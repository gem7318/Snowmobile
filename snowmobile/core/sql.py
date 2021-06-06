"""
:class:`SQL` contains utility methods to generate & execute
common SQL commands; :class:`~snowmobile.core.connection.Snowmobile` inherits
everything from this object and provides it with the .query() method for
statement execution.

.. note::
   The :attr:`~SQL.auto_run` attribute defaults to `True`, meaning that the
   ge sql will execute when a method is called; if set to `False`
   the method will return the sql as a string without executing.

   The :class:`SQL` object is primarily interacted with as a
   pre-instantiated attribute of :class:`~snowmobile.Snowmobile`; in these
   instances users can fetch the ge sql as a string either by:

   1. Providing *run=False* to any method called; this will override
      all behavior set by the current value of :attr:`auto_run`
   2. Setting the :attr:`auto_run` attribute to `False` on an existing
      instance of :class:`SQL`, which will replicate the behavior of
      `(1)` without needing to provide *run=False* to each method
      called on that instance

"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable

import pandas as pd

from . import Generic
from .configuration import Configuration
from .utils.parsing import p, up, strip as s
from .errors import SnowflakeObjectNotFound


class SQL(Generic):
    """SQL class for generation & execution of common sql commands.

    Intended to be interacted with as a parent of :class:`~snowmobile.Snowmobile`.

    .. note::
        *   All arguments except for :attr:`sn` are optional.
        *   The benefit of setting the other attributes on an instance of :class:`SQL`
            is to (optionally) avoid passing the same information to multiple methods
            when generating a variety of st around the same object.

    Attributes:
        nm (str):
            Object name to use in ge sql (e.g. 'some_table_name')
        obj (str):
            Object type to use in ge sql (e.g. 'table')
        schema (str):
            Schema to use when dot-prefixing sql; defaults to the schema with which the
            :attr:`sn` is connected to.
        auto_run (bool):
            Indicates whether to automatically execute the sql ge by a given
            method; defaults to *True*

    """

    def __init__(
        self,
        _query_func: Callable,
        _cfg: Configuration,
        nm: Optional[str] = None,
        schema: Optional[str] = None,
        obj: Optional[str] = None,
        auto_run: Optional[bool] = True,
    ):
        """Initializes a :class:`snowmobile.SQL` object."""
        super().__init__()
        
        _schema, self.nm = p(nm=nm)
        
        self.schema = schema or _schema or _cfg.connection.current.schema_name
        
        self.obj: str = obj or "table"
        self.auto_run: bool = auto_run
        
        self._query = _query_func
        self._cfg = _cfg
        
    # -- Information Schema ---------------------------------------------------
    
    def info_schema(
        self,
        loc: str,
        where: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        order_by: Optional[List] = None,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Generic case of selecting from information schema location."""
        _fields = self.fields(fields=fields)
        _order_by = self.order(by=order_by)
        _loc = f"information_schema.{loc}"
        _where = [w for w in where or list() if w]
        if _where:
            clauses = 'and'.join(f"\n\t{clause}" for clause in _where)
            _where = f"where\n{clauses}"
        sql = f"""
select
{_fields}
from {_loc}
{_where}
{_order_by}
"""
        _sql = s(sql, trailing=False, blanks=True)
        return self._query(_sql) if self(run) else _sql
    
    def table_info(
        self,
        nm: Optional[str] = None,
        fields: List[str] = None,
        restrictions: Dict[str, str] = None,
        order_by: List[Optional[str, int]] = None,
        all_schemas: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Query ``information_schema.tables`` for a given table or view.

        Args:
            nm (str):
                Table name, including schema if creating a stage outside of the
                current schema.
            fields (List[str]):
                List of fields to include in returned results (e.g.
                ['table_name', 'table_type', 'last_altered'])
            restrictions (List[str]):
                List of conditionals typed as literal components of a `where`
                clause (e.g.
                ["table_type = 'base table'", 'last_altered::date = current_date()']
                ).
            order_by (List[str]):
                List of fields or their ordinal positions to order the results by.
            all_schemas (bool):
                Include tables/views from all schemas; defaults to `False`.
            run (bool):
                Determines whether to run the ge sql or not; defaults to `None`
                which will reference the current value of the :attr:`auto_run` attribute
                which defaults to `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        # fmt: off
        try:
            schema, nm = p(nm)
            table, schema = (
                self._validate(
                    val=(nm or self.nm), nm='nm', attr_nm='nm'
                ),
                self._validate(
                    val=(schema or self.schema), nm='schema', attr_nm='schema'
                )
            )

        except ValueError as e:
            raise e

        restrictions = {
            **(restrictions or dict()),
            **{
                "lower(table_name)": f"'{table.lower()}'",
                "lower(table_schema)": f"'{schema.lower()}'",
            },
        }
        if all_schemas:
            _ = restrictions.pop("lower(table_schema)")

        sql = self._info_schema_generic(
            obj="table", fields=fields, restrictions=restrictions, order_by=order_by
        )
        # fmt: on

        return self._query(sql=sql) if self(run) else sql

    def column_info(
        self,
        nm: Optional[str] = None,
        fields: Optional[List] = None,
        restrictions: Optional[Dict] = None,
        order_by: Optional[List] = None,
        all_schemas: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Query ``information_schema.columns`` for a given table or view.

        Args:
            nm (str):
                Table name, including schema if creating a stage outside of the
                current schema.
            fields (List[str]):
                List of fields to include in returned results (e.g.
                ['ordinal_position', 'column_name', 'data_type'])
            restrictions (List[str]):
                List of conditionals typed as literal components of a `where`
                clause (e.g.["regexp_count(lower(column_name), 'tmstmp') = 0"]).
            order_by (List[str]):
                List of fields or their ordinal positions to order the results by.
            all_schemas (bool):
                Include tables/views from all schemas; defaults to `False`.
            run (bool):
                Determines whether to run the ge sql or not; defaults to `None`
                which will reference the current value of the :attr:`auto_run` attribute
                which defaults to `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        try:
            # fmt: off
            schema, nm = p(nm)
            table = self._validate(
                val=(nm or self.nm), nm='nm', attr_nm='nm'
            )
            schema = self._validate(
                val=(schema or self.schema), nm='schema', attr_nm='schema'
            )
            # fmt: on
        except ValueError as e:
            raise e
        restrictions = {
            **(restrictions or dict()),
            **{
                "lower(table_name)": f"'{table.lower()}'",
                "lower(table_schema)": f"'{schema.lower()}'",
            },
        }
        if all_schemas:
            _ = restrictions.pop("lower(table_schema)")

        sql = self._info_schema_generic(
            obj="column", fields=fields, restrictions=restrictions, order_by=order_by
        )

        return self._query(sql=sql) if self(run) else sql
    
    def columns(
        self,
        nm: Optional[str] = None,
        from_info_schema: bool = False,
        lower: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, List]:
        """Returns an ordered list of columns for a table or view.

        note:
            *   The default behavior of this method is to retrieve the columns
                for a table or view by selecting a single sample record
                from the table and extracting the column names directly off
                the returned :class:`pandas.DataFrame` due to the performance
                gains in selecting a sample record as opposed to querying the
                ``information_schema.columns``.
            *   This can be changed by passing `from_info_schema=False`.

        Args:
            nm (str):
                Name of table or view, including schema if the table or view is
                outside of the current schema.
            from_info_schema (bool):
                Indicates whether to retrieve columns via the
                ``information_schema.columns`` or by selecting a sample record
                from the table or view; defaults to `False`.
            lower (bool):
                Lower case each column in the list that's returned.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, List]):
            Either:
                1.  An ordered list of columns for the table or view, **or**
                2.  The query against the table or view as a :class:`str` of sql.

        """
        if from_info_schema:
            return self._columns_from_info_schema(nm=nm, lower=lower, run=run)
        else:
            return self._columns_from_sample(nm=nm, lower=lower, run=run)
        
    # -- Common Queries -------------------------------------------------------
    
    def select(
        self,
        nm: Optional[str] = None,
        n: Optional[int] = None,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Select `n` sample records from a table.

        Args:
            nm (str):
                Name of table or view to sample, including schema if the table
                or view is outside of the current schema.
            n (int):
                Number of records to return, implemented as a 'limit' clause
                in the query; defaults to 1.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        schema, nm = p(nm)
        try:
            # fmt: off
            schema, table = (
                self._validate(
                    val=(schema or self.schema), nm='schema', attr_nm='schema'
                ),
                self._validate(
                    val=(nm or self.nm), nm='nm', attr_nm='nm'
                )
            )
            # fmt: on
        except ValueError as e:
            raise e
        limit = f"limit {n or 1}" if n != -1 else str()
        sql = (
            f"""
            select
                *
            from {up(schema)}.{up(table)}
            {limit}
            """
        )
        return self._query(sql=sql) if self(run) else sql
     
    # noinspection PyBroadException
    def exists(self, nm: Optional[str] = None) -> bool:
        """Checks the existence of a table or view.

        Args:
            nm (str):
                Name of table or view, including schema if the table or view is
                outside of the current schema.

        Returns (bool):
            Boolean indication of whether or not the table or view exists.

        """
        try:
            _ = self.select(nm=nm, n=1)
            return True
        except:
            return False

    def is_distinct(self, nm: Optional[str] = None, field: Optional[str] = None) -> bool:
        """Checks if table `nm` is distinct on column `on_col`

        Args:
            nm (str):
                Table name.
            field (str):
                Column name.
                
        """
        try:
            return self.count(nm=nm, dst_of=field, as_perc=True) == 1
        except ValueError as e:
            raise e

    def count(
            self,
            nm: Optional[str] = None,
            of: Optional[str] = None,
            dst_of: Optional[str] = None,
            as_perc: Optional[bool] = None,
            run: Optional[bool] = None,
    ) -> Union[int, float]:
        """Number of records within a table or view.

        Args:
            nm (str):
                Table name, including schema if querying outside current schema.
            of (str):
                Column name (indistinct).
            dst_of (str):
                Column name (distinct).
            as_perc (bool):
                Option to return distinct count of the `dst_of` column as a
                percentage of the namespace depth of the table or view.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        schema, nm = p(nm)
        try:
            obj_schema = self._validate(
                val=(schema or self.schema), nm='obj_schema', attr_nm='schema'
            )
            obj_name = self._validate(
                val=(nm or self.nm), nm='obj_name', attr_nm='obj_name'
            )
        except ValueError as e:
            raise e
        
        _from = f"from {obj_schema}.{obj_name}"
        sql = f"select count(*) {_from}"
        if of:
            sql = f"select count({of}) {_from}"
        if dst_of:
            sql = f"select count(distinct {dst_of}) {_from}"
        if as_perc:
            if not dst_of:
                raise ValueError(
                    "`as_perc=True` pr without specifying `dst_of` column."
                )
            sql = f"select count(distinct {dst_of}) / count(*) {_from}"
            
        return self._query(sql=sql, as_scalar=True) if self(run) else sql
    
    def show(
        self,
        obj: str,
        in_loc: Optional[str] = None,
        names: bool = False,
        run: Optional[bool] = None,
        **kwargs,
    ) -> Union[pd.DataFrame, List[str], str]:
        """Show schema objects of typ 'obj', optionally 'in_loc'.

        Args:
            obj (str):
                Schema object type ('tables', 'file formats', etc).
            in_loc (str):
                Snowflake location ('in schema sandbox', 'in database prod', etc).
            names (bool):
                Return a list of schema object names only ('name' field).
            run (bool):
                Execute the ge sql or return it as a string.

        Returns (Union[pd.DataFrame, str]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`
                2.  The 'names' column of the results returned as a list
                3.  The ge query as a :class:`str` of sql
            
        """
        _in_loc = f" in {in_loc}" if in_loc else str()
        sql = s(f"show {obj}{_in_loc}")
        if self(run):
            result = self._query(sql, **kwargs)
            return (
                result
                if not names
                else result.snf.to_list(
                    'name' if not kwargs.get('lower') else 'NAME'
                )
            )
        return self._query(sql, **kwargs) if self(run) else sql
    
    # -- Metadata -------------------------------------------------------------
    
    def ddl(
        self,
        nm: Optional[str] = None,
        obj: Optional[str] = None,
        run: Optional[bool] = None,
    ) -> str:
        """Query the DDL for an schema object.

        Args:
            nm (str):
                Name of the object to get DDL for, including schema if object
                is outside of the current schema.
            obj (str):
                Type of object to get DDL for (e.g. 'table', 'view', 'file-format').
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (str):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        schema, nm = p(nm)
        try:
            # fmt: off
            obj, schema, nm = (
                self._validate(
                    val=(obj or self.obj), nm='obj', attr_nm='obj'
                ),
                self._validate(
                    val=(schema or self.schema), nm='schema', attr_nm='schema'
                ),
                self._validate(
                    val=(nm or self.nm), nm='nm', attr_nm='nm'
                )
            )
            # fmt: on
        except ValueError as e:
            raise e
        _nm = self._schema_object(nm=nm, schema=schema, typ=obj)
        sql = s(f"select get_ddl('{obj}', '{up(_nm)}') as ddl")
        return self._query(sql=sql).snf.to_list(n=1) if self(run) else sql
    
    def comment(
        self,
        nm: Optional[str] = None,
        obj: Optional[str] = None,
        set_as: Optional[str] = None,
        from_json: bool = False,
        as_json: bool = False,
        run: Optional[bool] = None,
        **kwargs,
    ) -> Union[str, Dict]:
        """Get or set comment on a schema object.

        Args:
            nm (str):
                Name of the schema object, including schema prefix if object
                is outside implicit scope of the current connection.
            obj (str):
                Type of schema object (e.g. 'table', 'schema', etc).
            set_as (str):
                Content to set as comment on schema object.
            from_json (bool):
                Parse schema object comment as a string of json and return it
                as a dictionary.
            as_json (bool):
                Dump contents of 'set_as' to a string of json prior to setting
                comment.
            run (bool):
                Indicates whether to execute generated sql or return as string;
                default is `True`.
            **kwargs:
                Keyword argument to pass to `json.loads(comment)` if
                *from_json=True*.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The schema object comment as a :class:`str`
                2.  The ge query as a :class:`str` of sql.
                3.  The schema object comment as a dictionary if *from_json=True*

        """
        # fmt: off
        if set_as:
            return self._set_comment(
                nm=nm,
                obj=obj,
                comment=set_as,
                as_json=as_json,
                run=run,
                **kwargs,
            )
        try:
            schema, nm = p(nm)
            obj, obj_schema, obj_name = (
                self._validate(
                    val=(obj or self.obj), nm='obj', attr_nm='obj'
                ).lower(),
                self._validate(
                    val=(schema or self.schema), nm='obj_schema', attr_nm='schema'
                ).lower(),
                self._validate(
                    val=(nm or self.nm), nm='obj_name', attr_nm='nm'
                ).lower()
            )
        except ValueError as e:
            raise e
        
        sql = self.info_schema(
            loc=self._cfg.sql.info_schema_loc(obj, stem=True),
            fields=['comment'],
            where=[
                f"lower({obj if obj != 'view' else 'table'}_name) = '{obj_name}'",
                self._c(
                    val=f"lower(table_schema) = '{obj_schema}'",
                    condition=bool(obj in ['table', 'view'])
                ),
            ],
            run=False,
        )
        
        if self(run):
            
            df = self._query(sql)
            
            if df.empty:
                raise SnowflakeObjectNotFound(
                    msg=(f"""
Object not found; \ndouble check that the schema object
exists and that the below sql is querying the intended
object:\n\n{sql}
"""
                         )
                )
            
            comment = df.snf.to_list('comment', n=1)
            return (
                comment if not from_json
                else
                json.loads(comment, **kwargs) if comment else dict()
            )
        
        # fmt: on
        return sql
    
    def last_altered(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.Timestamp]:
        """Last altered timestamp for a table or view.

        Args:
            nm (str):
                Table name, including schema if creating a stage outside of the
                current schema.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        try:
            sql = self.table_info(
                nm=nm,
                fields=["last_altered"],
                run=False,
            )
            return (
                self._query(sql=sql, as_scalar=True)
                if self(run)
                else sql
            )
        except AssertionError as e:
            raise e
    
    # -- Common DML Commands --------------------------------------------------

    def truncate(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.DataFrame]:
        """Truncate a table.

        Args:
            nm (str):
                Name of table, including schema if the table is outside of the
                current schema.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        schema, nm = p(nm)
        try:
            # fmt: off
            schema, name = (
                self._validate(
                    val=(schema or self.schema), nm='schema', attr_nm='schema'
                ),
                self._validate(
                    val=(nm or self.nm), nm='nm', attr_nm='nm'
                )
            )
            # fmt: on
        except ValueError as e:
            raise e
        sql = s(f"truncate table {up(schema)}.{up(name)}")
        return self._query(sql=sql) if self(run) else sql

    def drop(
        self,
        nm: Optional[str] = None,
        obj: Optional[str] = None,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Drop a ``Snowflake`` object.

        Args:
            nm (str):
                Name of the object to drop, including schema if creating a stage
                outside of the current schema.
            obj (str):
                Type of object to drop (e.g. 'table', 'schema', etc)
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        schema, nm = p(nm)
        try:
            # fmt: off
            obj_schema, obj_name, obj = (
                self._validate(
                    val=(schema or self.schema), nm='obj_schema', attr_nm='schema'
                ),
                self._validate(
                    val=(nm or self.nm), nm='obj_name', attr_nm='obj_name'
                ),
                self._validate(
                    val=(obj or self.obj), nm='obj', attr_nm='obj'
                )
            )
            # fmt: on
        except ValueError as e:
            raise e
        _name = self._schema_object(nm=obj_name, schema=obj_schema, typ=obj)
        sql = s(f"drop {obj} if exists {up(_name)}")
        return self._query(sql=sql) if self(run) else sql
    
    def clone(
        self,
        nm: Optional[str] = None,
        to: Optional[str] = None,
        obj: Optional[str] = None,
        run: Optional[bool] = None,
        replace: bool = False,
    ) -> Union[str, pd.DataFrame]:
        """Clone a ``Snowflake`` object.

        Warnings:
            *   Make sure to read `Snowflake's documentation
                <https://docs.snowflake.com/en/sql-reference/sql/create-clone.html>`_
                for restrictions and considerations when cloning objects.

        Note:
            *   In this specific method, the value pr to ``nm`` and ``to``
                can be a single object name, a single schema, or both in the
                form of `obj_schema.obj_name` depending on the desired outcome.
            *   Additionally, **at least one of the** ``nm`` **or** ``to``
                **arguments must be pr**.
            *   The defaults for the target object are constructed such that
                users can **either**:
                    1.  Clone objects to *other* schemas that inherit the
                        source object's *name* without specifying so in the
                        ``to`` argument, **or**
                    2.  Clone objects within the *current* schema that inherit
                        the source object's *schema* without specifying so in
                        the ``to`` argument.
            *   If providing a schema without a name to either argument, prefix
                the value pr with `__` to signify it's a schema and not
                a lower-level object to be cloned.
                    *   e.g. providing `nm='sample_table'` and
                        `to='__sandbox'` will clone `sample_table` from the
                        current schema to `sandbox.sample_table`.
            *   An assertion error will be raised raised if neither argument
                is specified as *this would result in a command to clone an
                object and store it in an object that has the same name &
                schema as the object being cloned*.

        Args:
            nm (str):
                Name of the object to clone, including schema if cloning an
                object outside of the current schema.
            to (str):
                Target name for cloned object, including schema if cloning an
                object outside of the current schema.
            obj (str):
                Type of object to clone (e.g. 'table', 'view', 'file-format');
                defaults to `table`.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.
            replace (bool):
                Indicates whether to replace an existing stage if pre-existing;
                default is `False`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        try:
            # fmt: off
            schema, nm = p(nm)
            to_schema, to = p(nm=to)
            obj, schema, nm = (
                self._validate(
                    val=(obj or self.obj), nm='obj', attr_nm='obj'
                ),
                self._validate(
                    val=(schema or self.schema), nm='schema', attr_nm='schema'
                ),
                self._validate(
                    val=(nm or self.nm), nm='nm', attr_nm='nm'
                )
            )

            to_schema, to = (
                to_schema or schema,
                to or nm
            )
            if not to_schema and not to:
                raise ValueError(
                    "At least one of '__schema' or 'name` must be pr "
                    "in the 'to' argument of sql.clone()."
                )
            if nm == to and schema == to_schema:
                raise ValueError(
                    f"Target object name & schema mirrors source object name/schema. "
                    f"Please provide a different value `to`"
                )
            # fmt: on
        except ValueError as e:
            raise e
        _create = self._create(replace=replace)
        _src = self._schema_object(nm=nm, schema=schema, typ=obj)
        _target = self._schema_object(nm=to, schema=to_schema, typ=obj)
        sql = s(f"{_create} {obj} {up(_src)} clone {up(_target)}")
        return self._query(sql=sql) if self(run) else sql
    
    def _set_comment(
        self,
        comment: str,
        nm: Optional[str] = None,
        obj: Optional[str] = None,
        as_json: bool = False,
        run: Optional[bool] = None,
        **kwargs,
    ) -> str:
        """Drop a ``Snowflake`` object.

        Args:
            comment (str):
                Value to set as comment on the schema object.
            nm (str):
                Name of the schema object to set comment on, including schema
                prefix if it's a table, view, or file format located outside
                of the current schema.
            obj (str):
                Type of schema object (e.g. 'table', 'schema', etc)
            as_json (bool):
                Dump comment to a string of json before setting it on the schema
                object.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.
            **kwargs:
                Keyword argument to pass to `json.dumps(comment, **kwargs)`
                if *as_json = True*.

        Returns (str):
            Db response from the statement as a string.

        """
        # fmt: off
        schema, nm = p(nm)
        try:
            obj, obj_schema, obj_name = (
                self._validate(
                    val=(obj or self.obj), nm='obj', attr_nm='obj'
                ).lower(),
                self._validate(
                    val=(schema or self.schema), nm='obj_schema', attr_nm='schema'
                ).lower(),
                self._validate(
                    val=(nm or self.nm), nm='obj_name', attr_nm='nm'
                ).lower()
            )
        except ValueError as e:
            raise e
        
        _comment = (
            comment
            if not as_json
            else json.dumps(comment, **kwargs)
        )
        _name = self._schema_object(nm=obj_name, schema=obj_schema, typ=obj)
        _sql = (
            f"""
            comment on {obj} {_name}
            is '{_comment}'
            """
        )
        sql = s(_sql, trailing=False, blanks=True)
        return self._query(sql, as_scalar=True) if self(run) else sql
    
    # -- Staging Operations ---------------------------------------------------

    def create_stage(
        self,
        nm_stage: str,
        nm_format: str,
        replace: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Create a staging table.

        Args:
            nm_stage (str):
                Name of stage to create, including schema if creating a stage
                outside of the current schema.
            nm_format (str):
                Name of file format to specify for the stage, including schema
                if using a format from outside of the current schema.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.
            replace (bool):
                Indicates whether to replace an existing stage if pre-existing;
                default is `False`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        create = self._create(replace=replace)
        sql = s(f"{create} stage {nm_stage} file_format = {nm_format};")
        return self._query(sql=sql) if self(run) else sql

    def put_file_from_stage(
        self,
        path: Union[Path, str],
        nm_stage: str,
        options: Optional[Dict] = None,
        ignore_defaults: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Generates a 'put' command into a staging table from a local file.

        Args:
            path (Union[Path, str]):
                Path to local data file as a :class:`pathlib.Path` or string.
            nm_stage (str):
                Name of the staging table to load into.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.
            options (dict):
                Optional arguments to add to `put` statement in addition to
                the values specified in the ``loading.put`` section
                of **snowmobile.toml**.
            ignore_defaults (bool):
                Option to ignore the values specified in **snowmobile.toml**;
                defaults to `False`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        path = Path(str(path))
        statement = [f"put file://{path.as_posix()} @{nm_stage}"]
        # fmt: off
        defaults = (
            dict() if ignore_defaults
            else self._cfg.loading.put.dict(by_alias=False)
        )
        options = {
            **defaults,
            **(options or dict()),
        }
        for k, v in options.items():
            statement.append(f"\t{k} = {str(v).lower() if isinstance(v, bool) else v}")
        # fmt: on
        _sql = "\n".join(statement)
        sql = s(_sql, trailing=False, whitespace=False, blanks=True)

        return self._query(sql=sql) if self(run) else sql

    def copy_into_table_from_stage(
        self,
        nm: str,
        nm_stage: str,
        options: Optional[Dict] = None,
        ignore_defaults: bool = False,
        run: Optional[bool] = None,
    ) -> Union[str, pd.DataFrame]:
        """Generates a command to copy data into a table from a staging table.

        Args:
            nm (str):
                Name of the object to drop, including schema if creating a stage
                outside of the current schema.
            nm_stage (str):
                Name of the staging table to load from.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.
            options (dict):
                Optional arguments to add to `put` statement in addition to
                the values specified in the ``loading.put`` section
                of **snowmobile.toml**.
            ignore_defaults (bool):
                Option to ignore the values specified in **snowmobile.toml**;
                defaults to `False`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        statement = [f"copy into {nm} from @{nm_stage}"]
        defaults = (
            self._cfg.loading.copy_into.dict(by_alias=False)
            if not ignore_defaults
            else dict()
        )
        options = {**defaults, **(options or dict())}
        for k, v in options.items():
            statement.append(f"\t{k} = {v}")
        _sql = "\n".join(statement)
        sql = s(_sql, trailing=False, whitespace=False, blanks=True)
        return self._query(sql=sql) if self(run) else sql

    # -- Current Connection Information ---------------------------------------

    def current(
        self, obj: str, run: Optional[bool] = None
    ) -> Union[str, Union[str, int]]:
        """Generic implementation of 'select current' for session-based objects.

        Args:
            obj (str):
                Type of object to retrieve information for (schema, session, ..).
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        _sql = f"select current_{obj}()"
        sql = s(_sql)
        return self._query(sql=sql).snf.to_list(n=1) if self(run) else sql

    def current_session(self, run: Optional[bool] = None) -> Union[str, pd.DataFrame]:
        """Select the current session."""
        return self.current(obj="session", run=run)

    def current_schema(self, run: Optional[bool] = None) -> Union[str, pd.DataFrame]:
        """Select the current schema."""
        return self.current(obj="schema", run=run)

    def current_database(self, run: Optional[bool] = None) -> Union[str, pd.DataFrame]:
        """Select the current database."""
        return self.current(obj="database", run=run)

    def current_warehouse(self, run: Optional[bool] = None) -> Union[str, pd.DataFrame]:
        """Select the current warehouse."""
        return self.current(obj="warehouse", run=run)

    def current_role(self, run: Optional[bool] = None) -> Union[str, pd.DataFrame]:
        """Select the current role."""
        return self.current(obj="role", run=run)

    # -- Generic 'use ___' Statements -----------------------------------------

    def use(self, nm: str, obj: str, run: Optional[bool] = None):
        """Generic implementation of 'use' command for schema objects.

        Args:
            nm (str):
                Name of object to use (schema name, warehouse name, role name, ..).
            obj (str):
                Type of object to use (schema, warehouse, role, ..).
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, pd.DataFrame]):
            Either:
                1.  The results of the query as a :class:`pandas.DataFrame`, or
                2.  The ge query as a :class:`str` of sql.

        """
        # fmt: off
        try:
            name = self._validate(
                val=(nm or self.nm), nm='nm', attr_nm='nm'
            )
        except ValueError as e:
            raise e
        # fmt: on
        _sql = f"use {obj} {up(name)}"
        sql = s(_sql)
        return self._query(sql=sql) if self(run) else sql

    def use_schema(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.DataFrame]:
        """Use schema command."""
        return self.use(obj="schema", nm=nm, run=run)

    def use_database(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.DataFrame]:
        """Use database command."""
        return self.use(obj="database", nm=nm, run=run)

    def use_warehouse(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.DataFrame]:
        """Use warehouse command."""
        return self.use(obj="warehouse", nm=nm, run=run)

    def use_role(
        self, nm: Optional[str] = None, run: Optional[bool] = None
    ) -> Union[str, pd.DataFrame]:
        """Use role command."""
        return self.use(obj="role", nm=nm, run=run)

    # -- Private and Static Methods -------------------------------------------

    @staticmethod
    def _validate(
        val: Optional[str, int], nm: str, attr_nm: Optional[str] = None
    ) -> str:
        """Validates the value of an argument passed to a method.

        This method is built to validate method arguments in instances where an
        unspecified argument can fall back to an attribute if it has been set.

        Each of the 'closing' variables below represents a different ending to
        a sentence within the exception message depending on the value pr
        from the method and if the attribute the argument falls back to has been
        set at the time the method is called.

        Args:
            val (Union[str, int]:
                Value to validate.
            nm (str):
                Name of argument in the method being called.
            attr_nm (str):
                Name of attribute to fall back to if the boolean representation
                of ``val`` is `False`.

        """
        if not val:
            closing1 = (
                "." if not attr_nm else f", nor is its fallback attribute '{attr_nm}'."
            )
            closing2 = (
                "."
                if not attr_nm
                else f" or set the '{attr_nm}' attribute before calling the method."
            )
            raise ValueError(
                f"\nValue pr for '{nm}' is not valid{closing1}\n"
                f"Please provide a valid value for '{nm}'{closing2}"
            )
        return val

    def _columns_from_info_schema(
        self, nm: Optional[str] = None, lower: bool = False, run: Optional[bool] = None
    ) -> Union[str, List]:
        """Retrieves list of columns for a table or view **from information schema**.

        Args:
            nm (str):
                Name of table or view, including schema if the table or view is
                outside of the current schema.
            lower (bool):
                Lower case each column in the list that's returned.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, List]):
            Either:
                1.  An ordered list of columns for the table or view, **or**
                2.  The query against ``information_schema.columns`` as a
                    :class:`str` of sql.

        """
        sql = self.column_info(
            nm=nm, fields=["ordinal_position", "column_name"], order_by=[1], run=False
        )
        if self(run):
            return [
                c.lower() if lower else c
                for c in self._query(sql).snf.to_list(col="column_name")
            ]
        else:
            return sql

    def _columns_from_sample(
        self, nm: Optional[str] = None, lower: bool = False, run: Optional[bool] = None
    ) -> Union[str, List]:
        """Retrieves a list of columns for a table or view from **sampling table**.

        Args:
            nm (str):
                Name of table or view, including schema if the table or view is
                outside of the current schema.
            lower (bool):
                Lower case each column in the list that's returned.
            run (bool):
                Indicates whether to execute ge sql or return as string;
                default is `True`.

        Returns (Union[str, List]):
            Either:
                1.  An ordered list of columns for the table or view, **or**
                2.  The query against the table or view as a :class:`str` of sql.

        """
        _sql = self.select(nm=nm, run=False, n=1)
        sql = s(_sql)
        if self(run):
            return [c for c in self._query(sql, lower=lower).columns]
        else:
            return sql

    def _info_schema_generic(
        self,
        obj: str,
        fields: List[str] = None,
        restrictions: Dict[str, str] = None,
        order_by: Optional[List] = None,
    ) -> str:
        """Generic case of selecting from information schema tables/columns.

        Queries different parts of the information schema based on an ``obj``
        and the mapping of object type to information schema defined in
        `snowmobile.core.sql._map_information_schema.py`.

        """
        info_schema_loc = self._cfg.sql.info_schema_loc(obj=obj)
        fields = self.fields(fields=fields)
        where = self.where(restrictions=restrictions)
        order_by = self.order(by=order_by)

        sql = f"""
select
{fields}
from {info_schema_loc}
{where}
{order_by}
"""
        return s(sql, trailing=False, blanks=True)

    @staticmethod
    def order(by: List[Union[int, str]]) -> str:
        """Generates 'order by' clause from a list of fields or field ordinal positions."""
        if by:
            order_by_fields = ",".join(str(v) for v in by)
            return f"order by {order_by_fields}"
        else:
            return str()

    @staticmethod
    def where(restrictions: Dict) -> str:
        """Generates a 'where' clause based on a dictionary of restrictions.

        Args:
            restrictions (dict):
                A dictionary of conditionals where each key/value pair
                respectively represents the left/right side of a condition
                within a 'where' clause.

        Returns (str):
            Formatted where clause.

        """
        if restrictions:
            args = [
                f"{str(where_this)} = {str(equals_this)}"
                for where_this, equals_this in restrictions.items()
            ]
            args = "\n\tand ".join(args)
            return f"where\n\t{args}"
        else:
            return str()

    @staticmethod
    def fields(fields: Optional[List[str]] = None) -> str:
        """Utility to generate fields within a 'select' statement."""
        return "\n".join(
            f'\t{"," if i > 1 else ""}{f}'
            for i, f in enumerate(fields or ["*"], start=1)
        )
    
    @staticmethod
    def _c(val: str, condition: bool) -> str:
        """Checks val based on a condition."""
        return val if condition else str()
    
    @staticmethod
    def _create(replace: bool = False):
        """Utility to generate 'create'/'create or replace' based on an argument."""
        return "create" if not replace else "create or replace"

    def _r(self, run: Union[bool, None]) -> bool:
        """Determines whether or not to execute a piece of sql.

        Used in all subsequent methods containing a `run` argument.

        Args:
            run (Union[bool, None]):
                The value from a method's `run` argument.

        Returns (bool):
            Boolean value indicating whether or not to execute the sql ge by
            the method to which the value of `run` was passed.

        note:
            *   The default value of `run` in all subsequent methods is ``None``.
            *   When any method of :class:`SQL` containing a `run` argument is called,
                the argument's value is passed to this method which returns either:
                    1.  The argument's value if it is a valid bool (i.e. a user-pr
                        value to the method), or
                    2.  The boolean representation of the current :attr:`auto_run`
                        attribute (`True` by default).

        """
        if isinstance(run, bool):
            return run
        else:
            return bool(self.auto_run)
    
    @staticmethod
    def _schema_object(nm: str, schema: str, typ: str) -> str:
        """Returns schema object as a string based on its 'typ'."""
        return (
            nm
            if typ.lower() not in ['table', 'view', 'file_format']
            else f"{schema}.{nm}"
        )

    def _reset(self) -> SQL:
        self.schema = self._cfg.connection.current.schema_name
        self.nm = None
        self.obj = "table"
        return self

    def __call__(self, run: bool) -> bool:
        return self._r(run)

    def __str__(self) -> str:
        return f"snowmobile.SQL(creds='{self._cfg.connection.creds}')"

    def __repr__(self) -> str:
        return f"snowmobile.SQL(creds='{self._cfg.connection.creds}')"
