"""
Base class for all :class:`Statement` objects.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Union, Tuple, List

import pandas as pd
import sqlparse

from pydantic import BaseModel, Field

from pandas.io.sql import DatabaseError as pdDataBaseError
from snowflake.connector.errors import DatabaseError, ProgrammingError

from . import ExceptionHandler, Section, Name, errors, cfg
from . import Generic  # isort: skip
from .tag import Attrs
from .connection import Snowmobile


class Time(BaseModel):
    """
    Container for execution time info.
    """
    
    #: int: Unix timestamp statement is started
    started: int = Field(default_factory=int)
    
    #: int: Unix timestamp statement is completed
    ended: int = Field(default_factory=int)
    
    def __init__(self, **data):
        super().__init__(**data)
    
    def __int__(self):
        """Execution time in seconds."""
        return int(self.ended - self.started)
    
    def __str__(self):
        """Execution time as a string for console output."""
        return (
            f"{int(self)}s"
            if int(self) < 60
            else f"{int(int(self) / 60)}m"
        )


class Statement(Attrs, Name, Generic):
    """Base class for all :class:`Statement` objects.

    Home for attributes and methods that are associated with **all** statement
    objects, generic or QA.

    Attributes:
        sn (snowmobile.connect):
            :class:`snowmobile.connect` object.
        statement (Union[sqlparse.sql.Statement, str]):
            A :class:`sqlparse.sql.Statement` object.
        index (int):
            The context-specific index position of a statement within a script;
            can be `None`.
        patterns (config.Pattern):
            :class:`config.Pattern` object for more succinct access to
            values specified in **snowmobile.toml**.
        results (pd.DataFrame):
            The results of the statement if executed as a :class:`pandas.DataFrame`.
        outcome (int):
            Numeric indicator of outcome; defaults to `0` and is modified
            based on the outcome of statement execution and/or QA validation
            for derived classes.
        outcome_txt (str):
            Plain text of outcome ('skipped', 'failed', 'completed', 'passed').
        outcome_html (str):
            HTML text for the outcome as an admonition/information banner
            based on the following mapping of :attr:`outcome_txt` to
            admonition argument:
                *   `failed` ------> `warning`
                *   `completed` --> `info`
                *   `passed` -----> `success`
        start_time (int):
            Unix timestamp of the query start time if executed; 0 otherwise.
        end_time (int):
            Unix timestamp of the query end time if executed; 0 otherwise.
        execution_time (int):
            Execution time of the query in seconds if executed; 0 otherwise.
        execution_time_txt (str):
            Plain text description of execution time if executed; returned in
            seconds if execution time is less than 60 seconds, minutes otherwise.
        first_keyword (sqlparse.sql.Token):
            The first keyword within the statement as a :class:`sqlparse.sql.Token`.
        sql (str):
            The sql associated with the statement as a raw string.

    """

    # fmt: off
    PROCESS_OUTCOMES: Dict[Any, Any] = {
        0: ("-", ""),
        
        # -- start: base
        1: ("-", "error: execution"),
        2: ("success", "completed"),
        # -- end: base
        
        # -- start: derived
        -3: ("success", "passed"),
        -2: ("warning", "failed"),
        -1: ("-", "error: post-processing"),
        # -- end: derived
        
    }

    DERIVED_FAILURE_MAPPING = {
        'qa-diff': errors.QADiffFailure,
        'qa-empty': errors.QAEmptyFailure
    }
    # fmt: on

    def __init__(
        self,
        sn: Snowmobile,
        statement: Union[sqlparse.sql.Statement, str],
        index: Optional[int] = None,
        attrs_raw: Optional[str] = None,
        e: Optional[ExceptionHandler] = None,
        **kwargs,
    ):
        Generic.__init__(self)

        self._index: int = index
        self._outcome: int = int()

        self.outcome: bool = True
        self.executed: bool = bool()

        # self.sn = sn
        self.statement: sqlparse.sql.Statement = sn.cfg.script.ensure_sqlparse(
            statement
        )

        self.patterns: cfg.Pattern = sn.cfg.script.patterns
        self.results: pd.DataFrame = pd.DataFrame()

        #: Time: Execution time info
        self.time: Time = Time()
        
        self.start_time: int = int()
        self.end_time: int = int()
        self.execution_time: int = int()
        self.execution_time_txt: str = str()

        Attrs.__init__(self, sn=sn, raw=attrs_raw)
        self._sql = sn.cfg.script.strip_comments(s=self.statement)
        parsed, self._nm_intl = self.parse()
        self.update(parsed)
        
        Name.__init__(
            self,
            index=index,
            sql=self.sql(),
            nm_pr=self._nm_intl,
            configuration=self.sn.cfg,
        )

        self.e = e or ExceptionHandler(within=self)

    def sql(
        self, set_as: Optional[str] = None, tag: bool = False,
    ) -> Union[str, Statement]:
        """Raw sql from statement, including result limit if enabled."""
        if set_as:
            self._sql = set_as
            return self
        if tag:
            _attrs = self.tag(raw=False, namespace=True)
            if _attrs:
                _tag = self.sn.cfg.script.tag_from_attrs(
                    attrs=_attrs,
                    nm=_attrs.get('name', self.nm()),
                    wrap=False,
                )
            else:
                _tag = self.nm()
            tag = self.sn.cfg.script.wrap(_tag)
            return f"{tag}\n{self._sql}"
        if (
            self.sn.cfg.script.result_limit in [-1, 0]
            or self._sql.split('\n')[-1].strip().startswith('limit')
            or not self._sql.split('\n')[0].strip().lower().startswith('select')
        ):
            return self._sql
        return f"{self._sql}\nlimit {self.sn.cfg.script.result_limit}"

    def parse(self) -> Tuple[Dict, str]:
        """Parses tag contents into a valid dictionary.

        Uses the values specified in **snowmobile.toml** to parse a
        raw string of statement attributes into a valid dictionary.

        note:
            *   If :attr:`is_multiline` is `True` and `name` is not included
                within the arguments, an assertion error will be thrown.
            *   If :attr:`is_multiline` is `False`, the raw string within
                the wrap will be treated as the name.
            *   The :attr:`wrap` attribute is set once parsing is completed
                and name has been validated.

        Returns (dict):
            Parsed wrap arguments as a dictionary.

        """
        if not self.is_tagged:
            return dict(), str()

        if self.is_multiline:
            attrs_parsed = self.sn.cfg.script.parse_str(block=self.tag(raw=True))
            if "name" in attrs_parsed:
                name = attrs_parsed.pop("name")
            else:
                try:
                    name = self.sn.cfg.script.parse_name(raw=self.tag(raw=True))
                except errors.InvalidTagsError as e:
                    raise e

            return attrs_parsed, name

        return dict(), self.tag(raw=True)

    def start(self):
        """Sets :attr:`start_time` attribute."""
        self.start_time = time.time()

    def end(self):
        """Updates execution time attributes.

        In namespace, sets:
            *   :attr:`end_time`
            *   :attr:`execution_time`
            *   :attr:`execution_time_txt`

        """
        self.time.ended = self.end_time = time.time()
        self._outcome, self.outcome, self.executed = 2, True, True
        self.execution_time = int(self.end_time - self.start_time)
        self.execution_time_txt = (
            f"{self.execution_time}s"
            if self.execution_time < 60
            else f"{int(self.execution_time/60)}m"
        )

    def trim(self) -> str:
        """Statement as a string including only the sql and a single-line wrap name.

        note:
            The wrap name used here will be the user-pr wrap from the
            original script or a    generated :attr:`Name.nm` if a wrap was not
            provided for a given statement.

        """
        _open, _close = self.sn.cfg.script.tag()
        return f"{_open}{self.nm()}{_close}\n{self.sql()};\n"

    @property
    def is_derived(self):
        """Indicates whether or not it's a generic or derived (QA) statement."""
        return self.anchor() in self.sn.cfg.QA_ANCHORS

    @property
    def lines(self) -> List[str]:
        """Returns each line within the statement as a list."""
        return self.sql().split("\n")

    def as_section(self, incl_sql_tag: Optional[bool] = None, result_wrap: Optional[str] = None) -> Section:
        """Returns current statement as a :class:`Section` object."""
        attrs = self.tag(namespace=True)
        results = attrs.get('results')
        if results and results.empty:
            _ = attrs.pop('results')
            
        return Section(
            index=self.index,
            h_contents=self.nm(),
            parsed=self.tag(namespace=True),
            raw=self.tag(raw=True),
            sql=self.sql(),
            cfg=self.sn.cfg,
            results=self.results,
            incl_sql_tag=incl_sql_tag,
            is_multiline=self.is_multiline,
            result_wrap=result_wrap,
        )

    def set_state(
        self,
        index: Optional[int] = None,
        ctx_id: Optional[int] = None,
        in_context: Optional[bool] = None,
        filters: dict = None,
    ) -> Statement:
        """Sets current state/context on a statement object.

        Args:
            ctx_id (int):
                Unix timestamp the :meth:`script.filter()` context manager was
                invoked.
            filters (dict):
                Kwargs passed to :meth:`script.filter()`.
            index (int):
                Integer to set as the statement's index position.

        """
        if index:
            self.index = index
        if ctx_id:
            self.e.set(ctx_id=ctx_id)
        if isinstance(in_context, bool):
            self.e.set(in_context=in_context)
        if filters:
            super().scope(**filters)
        return self

    def reset(
        self,
        index: bool = False,
        ctx_id: bool = False,
        in_context: bool = False,
        scope: bool = False,
    ) -> Statement:
        """Resets attributes on the statement object to reflect as if read from source.

        In its current form, includes:
            *   Resetting the statement/wrap's index to their original values.
            *   Resetting the :attr:`is_included` attribute of the statement's
                :attr:`wrap` to `True`.
            *   Populating :attr:`error_last` with errors from current context.
            *   Caching current context's timestamp and resetting back to `None`.

        """
        if index:
            self.index = self._index
        if ctx_id:
            self.e.reset(ctx_id=True)
        if in_context:
            self.e.reset(in_context=True)
        if scope:
            super().scope(**{})
        return self

    def process(self):
        """Used by derived classes for post-processing the returned results."""
        return self

    def run(
        self,
        as_df: bool = True,
        lower: bool = True,
        render: bool = False,
        on_error: Optional[str] = None,
        on_exception: Optional[str] = None,
        on_failure: Optional[str] = None,
        ctx_id: Optional[int] = None,
    ) -> Statement:
        """Run method for all statement objects.

        Args:
            as_df (bool):
                Store results of query as :class:`pandas.DataFrame` or
                :class:`SnowflakeCursor`.
            lower (bool):
                Lower case column names in :attr:`results` DataFrame if
                `as_df=True`.
            render (bool):
                Render the sql executed as markdown.
            on_error (str):
                Behavior if an execution/database error is encountered
                    * `None`: default behavior, exception will be raised
                    * `c`: continue with execution
            on_exception (str):
                Behavior if an exception is raised in the **post-processing**
                of results from a derived class of :class:`Statement` (
                :class:`Empty` and :class:`Diff`).
                    * `None`: default behavior, exception will be raised
                    * `c`: continue with execution
            on_failure (str):
                Behavior if no error is encountered in execution or post-processing
                but the result of the post-processing has turned the statement's
                :attr:`outcome` attribute to False, indicating the results
                returned by the statement have failed validation.
                    * `None`: default behavior, exception will be raised
                    * `c`: continue with execution

        Returns (Statement):
            Statement object post-executing query.

        """

        self.e.set(ctx_id=(ctx_id or -1))
        try:
            if self:
                self.start()
                self.time.started = time.time()
                self.results = self.sn.query(self.sql(), as_df=as_df, lower=lower)
                self.end()
                self.e.set(outcome=2)

        except (ProgrammingError, pdDataBaseError, DatabaseError) as e:
            self.e.collect(e=e).set(outcome=1)

        finally:  # only when execution did not raise database error
            if self.e.outcome != 1:
                self.process()
                
        # fmt: off
        if (
            self.e.seen(             # db error raised during execution -------
                of_type=errors.db_errors, to_raise=True
            )
            and on_error != "c"      # stop on execution error ----------------
        ):
            raise self.e.get(
                of_type=errors.db_errors,
                to_raise=True,
                first=True,
            )
        
        if (
            self.e.seen(             # post-processing error occurred ---------
                of_type=errors.StatementPostProcessingError,
                to_raise=True,
            )
            and on_exception != "c"  # stop on post-processing exception ------
        ):
            raise self.e.get(
                of_type=errors.StatementPostProcessingError,
                to_raise=True,
                first=True,
            )
        
        if (
            self.is_derived        # is child class with `.process()` method --
            and not self.outcome   # outcome of `.process()` did not pass -----
            and on_failure != "c"  # stop on failure of `.process()` ----------
        ):
            raise self.e.get(
                of_type=list(self.DERIVED_FAILURE_MAPPING.values()),
                to_raise=True,
                first=True,
            )
        # fmt: on

        if render:
            self.render()

        return self

    @staticmethod
    def _validate_parsed(attrs_parsed: Dict):
        """Returns args to verify 'name' attribute is present in a multiline wrap."""
        condition, msg = (
            attrs_parsed.get("name"),
            f"Required attribute 'name' not found in multi-line wrap's "
            f"arguments;\n attributes found are: {','.join(list(attrs_parsed))}",
        )
        return condition, msg

    def outcome_txt(self, _id: Optional[int] = None) -> str:
        """Outcome as a string."""
        return self.PROCESS_OUTCOMES[_id or self.e.outcome or 0][1]

    @property
    def outcome_html(self) -> str:
        """Outcome as an html admonition banner."""
        # TODO: Move this to patterns
        alert = self.PROCESS_OUTCOMES[self.e.outcome or 0][0]
        return f"""
<div class="alert-{alert}">
<center><b>====/ {self.outcome_txt()} /====</b></center>
</div>""".strip()

    def __len__(self):
        """Number of lines in the statement."""
        return len(self.lines)

    def __bool__(self):
        """Determined by the value of :attr:`Name.is_included`."""
        return self.is_included

    def __str__(self) -> str:
        return f"Statement('{self.nm()}')"

    def __repr__(self) -> str:
        return f"Statement('{self.nm()}')"
