/*: -----------------------------------------------------------------------
    ** This file was stripped of all comments and exported by Snowmobile **
    ----------------------------------------------------------------------- :*/

/*-
__markup_no_results.sql__
__description***:
This script stores the test cases for `snowmobile.Markup`.
-*/

/*-create temp table~sample_table-*/
create or replace temp table sample_table as
	select 1 as dummy_dim, 1 as dummy_exclude, 1 as dummy_col
union
	select 2 as dummy_dim, 1 as dummy_exclude, 1 as dummy_col;

/*-
__intra-statement-marker__
__description: This is a sample intra statement marker.
-*/

/*-select data~sample select statement-*/
select * from sample_table;

/*-
__Appendix__
__other***:
- This is a sample marker after the last statement in the script.
-*/
