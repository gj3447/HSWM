
son_in_law(X, Y) :-
    child(X, A),
    husband(A, Y).

son(X, Y) :-
    child(X, Y),
    male(Y).

female(X) :-
    gender(X, "female").

:- dynamic prolog_load_file/2.
:- multifile prolog_load_file/2.


daughter(X, Y) :-
    child(X, Y),
    female(Y).

father_in_law(X, Y) :-
    married(X, A),
    father(A, Y).

:- multifile prolog_list_goal/1.


:- dynamic portray/1.
:- multifile portray/1.


mother_in_law(X, Y) :-
    married(X, A),
    mother(A, Y).

father(X, Y) :-
    parent(X, Y),
    male(Y).

:- dynamic expand_answer/2.
:- multifile expand_answer/2.


child(X, Y) :-
    parent(Y, X).

male_first_cousin_once_removed(X, Y) :-
    cousin(X, A),
    son(A, Y),
    X\=Y.

female_first_cousin_once_removed(X, Y) :-
    cousin(X, A),
    daughter(A, Y),
    X\=Y.

brother(X, Y) :-
    sibling(X, Y),
    male(Y).

mother(X, Y) :-
    parent(X, Y),
    female(Y).

male_second_cousin(X, Y) :-
    parent(X, A),
    parent(Y, B),
    cousin(A, B),
    male(Y),
    X\=Y.

female_second_cousin(X, Y) :-
    parent(X, A),
    parent(Y, B),
    cousin(A, B),
    female(Y),
    X\=Y.

married(X, Y) :-
    parent(Child, X),
    parent(Child, Y),
    X\=Y.

male(X) :-
    gender(X, "male").

sister(X, Y) :-
    sibling(X, Y),
    female(Y).

male_cousin(X, Y) :-
    cousin(X, Y),
    male(Y).

nonbinary(X) :-
    gender(X, "nonbinary").

:- dynamic exception/3.
:- multifile exception/3.


female_cousin(X, Y) :-
    cousin(X, Y),
    female(Y).

sibling(X, Y) :-
    parent(X, A),
    parent(Y, A),
    X\=Y.

:- dynamic resource/2.
:- multifile resource/2.


:- dynamic term_expansion/2.
:- multifile term_expansion/2.


:- dynamic parent/2.

parent("Cristal Showers", "Elvin Ybarra").
parent("Cristal Showers", "Kisha Ybarra").
parent("Elvin Ybarra", "Ruby Ybarra").
parent("Elvin Ybarra", "Zachery Ybarra").
parent("Gale Ybarra", "Elvin Ybarra").
parent("Gale Ybarra", "Kisha Ybarra").
parent("Ivan Ochs", "Hosea Ochs").
parent("Ivan Ochs", "Shawna Ochs").
parent("Katherine Showers", "Cristal Showers").
parent("Katherine Showers", "Darrel Showers").
parent("Larue Dorsett", "Perla Dorsett").
parent("Larue Dorsett", "Von Dorsett").
parent("Monika Crim", "Glenda Ochs").
parent("Monika Crim", "Ivan Ochs").
parent("Octavio Ybarra", "Elvin Ybarra").
parent("Octavio Ybarra", "Kisha Ybarra").
parent("Perla Dorsett", "Elvin Ybarra").
parent("Perla Dorsett", "Kisha Ybarra").
parent("Rosella Ochs", "Glenda Ochs").
parent("Rosella Ochs", "Ivan Ochs").
parent("Ruby Ybarra", "Francis Tooley").
parent("Ruby Ybarra", "Hoa Tooley").
parent("Shawna Ochs", "Ruby Ybarra").
parent("Shawna Ochs", "Zachery Ybarra").
parent("Stan Shattuck", "Randall Shattuck").
parent("Stan Shattuck", "Violet Shattuck").
parent("Trisha Crim", "Austin Crim").
parent("Trisha Crim", "Monika Crim").
parent("Violet Shattuck", "Cristal Showers").
parent("Violet Shattuck", "Darrel Showers").
parent("Alejandra Driskell", "Geoffrey Driskell").
parent("Alejandra Driskell", "Lara Driskell").
parent("Cleveland Johansen", "Minerva Johansen").
parent("Cleveland Johansen", "Saul Johansen").
parent("Eric Hoagland", "Lyndia Hoagland").
parent("Eric Hoagland", "Terence Hoagland").
parent("Hank Messenger", "Jackie Messenger").
parent("Hank Messenger", "Jason Messenger").
parent("Jackie Messenger", "Cleveland Johansen").
parent("Jackie Messenger", "Rosalee Johansen").
parent("Jason Messenger", "Selena Messenger").
parent("Jason Messenger", "Warren Messenger").
parent("Jewel Messenger", "Jackie Messenger").
parent("Jewel Messenger", "Jason Messenger").
parent("Linwood Messenger", "Boyd Messenger").
parent("Linwood Messenger", "Georgette Messenger").
parent("Lurline Messenger", "Jewel Messenger").
parent("Lurline Messenger", "Linwood Messenger").
parent("Lyndia Hoagland", "Jackie Messenger").
parent("Lyndia Hoagland", "Jason Messenger").
parent("Minerva Johansen", "Maira Witt").
parent("Minerva Johansen", "Nathan Witt").
parent("Rodrick Johansen", "Cleveland Johansen").
parent("Rodrick Johansen", "Rosalee Johansen").
parent("Rosalee Johansen", "Geoffrey Driskell").
parent("Rosalee Johansen", "Lara Driskell").
parent("Sara Messenger", "Selena Messenger").
parent("Sara Messenger", "Warren Messenger").
parent("Scotty Messenger", "Jackie Messenger").
parent("Scotty Messenger", "Jason Messenger").

cousin(X, Y) :-
    parent(X, A),
    parent(Y, B),
    sibling(A, B),
    X\=Y.

:- dynamic goal_expansion/4.
:- multifile goal_expansion/4.


uncle(X, Y) :-
    parent(X, A),
    brother(A, Y).

:- dynamic term_expansion/4.
:- multifile term_expansion/4.


aunt(X, Y) :-
    parent(X, A),
    sister(A, Y).

second_uncle(X, Y) :-
    great_grandparent(X, A),
    brother(A, Y).

:- dynamic gender/2.

gender("Austin Crim", "male").
gender("Cristal Showers", "female").
gender("Darrel Showers", "male").
gender("Elvin Ybarra", "male").
gender("Francis Tooley", "male").
gender("Gale Ybarra", "male").
gender("Glenda Ochs", "female").
gender("Hoa Tooley", "female").
gender("Hosea Ochs", "male").
gender("Ivan Ochs", "male").
gender("Katherine Showers", "female").
gender("Kisha Ybarra", "female").
gender("Larue Dorsett", "female").
gender("Monika Crim", "female").
gender("Octavio Ybarra", "male").
gender("Perla Dorsett", "female").
gender("Randall Shattuck", "male").
gender("Rosella Ochs", "female").
gender("Ruby Ybarra", "female").
gender("Shawna Ochs", "female").
gender("Stan Shattuck", "male").
gender("Trisha Crim", "female").
gender("Violet Shattuck", "female").
gender("Von Dorsett", "male").
gender("Zachery Ybarra", "male").
gender("Alejandra Driskell", "female").
gender("Boyd Messenger", "male").
gender("Cleveland Johansen", "male").
gender("Eric Hoagland", "male").
gender("Geoffrey Driskell", "male").
gender("Georgette Messenger", "female").
gender("Hank Messenger", "male").
gender("Jackie Messenger", "female").
gender("Jason Messenger", "male").
gender("Jewel Messenger", "female").
gender("Lara Driskell", "female").
gender("Linwood Messenger", "male").
gender("Lurline Messenger", "female").
gender("Lyndia Hoagland", "female").
gender("Maira Witt", "female").
gender("Minerva Johansen", "female").
gender("Nathan Witt", "male").
gender("Rodrick Johansen", "male").
gender("Rosalee Johansen", "female").
gender("Sara Messenger", "female").
gender("Saul Johansen", "male").
gender("Scotty Messenger", "male").
gender("Selena Messenger", "female").
gender("Terence Hoagland", "male").
gender("Warren Messenger", "male").

second_aunt(X, Y) :-
    great_grandparent(X, A),
    sister(A, Y).

great_grandson(X, Y) :-
    great_grandchild(X, Y),
    male(Y).

:- multifile prolog_predicate_name/2.


:- multifile message_property/2.


:- dynamic pyrun/2.

pyrun(A, B) :-
    read_term_from_atom(A, C, [variable_names(B)]),
    call(C).

great_granddaughter(X, Y) :-
    great_grandchild(X, Y),
    female(Y).

great_grandchild(X, Y) :-
    great_grandparent(Y, X).

:- multifile prolog_clause_name/2.


daughter_in_law(X, Y) :-
    child(X, A),
    wife(A, Y).

great_grandfather(X, Y) :-
    great_grandparent(X, Y),
    male(Y).

sister_in_law(X, Y) :-
    married(X, A),
    sister(A, Y).

great_grandmother(X, Y) :-
    great_grandparent(X, Y),
    female(Y).

brother_in_law(X, Y) :-
    married(X, A),
    brother(A, Y).

:- dynamic file_search_path/2.
:- multifile file_search_path/2.

file_search_path(library, A) :-
    user:library_directory(A).
file_search_path(swi, A) :-
    system:current_prolog_flag(home, A).
file_search_path(swi, A) :-
    system:current_prolog_flag(shared_home, A).
file_search_path(library, app_config(lib)).
file_search_path(library, swi(library)).
file_search_path(library, swi(library/clp)).
file_search_path(library, A) :-
    system:'$ext_library_directory'(A).
file_search_path(path, A) :-
    system:
    (   getenv('PATH', B),
        current_prolog_flag(path_sep, C),
        atomic_list_concat(D, C, B),
        '$member'(A, D)
    ).
file_search_path(user_app_data, A) :-
    system:'$xdg_prolog_directory'(data, A).
file_search_path(common_app_data, A) :-
    system:'$xdg_prolog_directory'(common_data, A).
file_search_path(user_app_config, A) :-
    system:'$xdg_prolog_directory'(config, A).
file_search_path(common_app_config, A) :-
    system:'$xdg_prolog_directory'(common_config, A).
file_search_path(app_data, user_app_data('.')).
file_search_path(app_data, common_app_data('.')).
file_search_path(app_config, user_app_config('.')).
file_search_path(app_config, common_app_config('.')).
file_search_path(app_preferences, user_app_config('.')).
file_search_path(user_profile, app_preferences('.')).
file_search_path(app, swi(app)).
file_search_path(app, app_data(app)).
file_search_path(working_directory, A) :-
    system:working_directory(A, A).
file_search_path(autoload, swi(library)).
file_search_path(autoload, pce(prolog/lib)).
file_search_path(autoload, app_config(lib)).
file_search_path(autoload, Dir) :-
    '$autoload':'$ext_library_directory'(Dir).
file_search_path(pack, app_data(pack)).
file_search_path(library, PackLib) :-
    '$pack':pack_dir(_Name, prolog, PackLib).
file_search_path(foreign, PackLib) :-
    '$pack':pack_dir(_Name, foreign, PackLib).
file_search_path(app, AppDir) :-
    '$pack':pack_dir(_Name, app, AppDir).

:- dynamic resource/3.
:- multifile resource/3.


great_grandparent(X, Y) :-
    grandparent(X, Z),
    parent(Z, Y).

friend(X, Y) :-
    friend_(X, Y).
friend(X, Y) :-
    friend_(Y, X).

grandson(X, Y) :-
    grandchild(X, Y),
    male(Y).

:- dynamic friend_/2.

friend_("Cristal Showers", "Francis Tooley").
friend_("Cristal Showers", "Glenda Ochs").
friend_("Cristal Showers", "Ivan Ochs").
friend_("Cristal Showers", "Monika Crim").
friend_("Cristal Showers", "Lara Driskell").
friend_("Cristal Showers", "Rodrick Johansen").
friend_("Darrel Showers", "Hoa Tooley").
friend_("Darrel Showers", "Trisha Crim").
friend_("Elvin Ybarra", "Stan Shattuck").
friend_("Elvin Ybarra", "Rodrick Johansen").
friend_("Elvin Ybarra", "Selena Messenger").
friend_("Francis Tooley", "Rosella Ochs").
friend_("Francis Tooley", "Eric Hoagland").
friend_("Francis Tooley", "Nathan Witt").
friend_("Gale Ybarra", "Lyndia Hoagland").
friend_("Glenda Ochs", "Larue Dorsett").
friend_("Glenda Ochs", "Lyndia Hoagland").
friend_("Glenda Ochs", "Maira Witt").
friend_("Hoa Tooley", "Stan Shattuck").
friend_("Hoa Tooley", "Cleveland Johansen").
friend_("Hoa Tooley", "Geoffrey Driskell").
friend_("Hoa Tooley", "Jason Messenger").
friend_("Hosea Ochs", "Shawna Ochs").
friend_("Hosea Ochs", "Jackie Messenger").
friend_("Ivan Ochs", "Katherine Showers").
friend_("Ivan Ochs", "Trisha Crim").
friend_("Ivan Ochs", "Von Dorsett").
friend_("Ivan Ochs", "Lurline Messenger").
friend_("Ivan Ochs", "Sara Messenger").
friend_("Katherine Showers", "Octavio Ybarra").
friend_("Katherine Showers", "Ruby Ybarra").
friend_("Katherine Showers", "Geoffrey Driskell").
friend_("Kisha Ybarra", "Cleveland Johansen").
friend_("Kisha Ybarra", "Eric Hoagland").
friend_("Larue Dorsett", "Monika Crim").
friend_("Larue Dorsett", "Lurline Messenger").
friend_("Larue Dorsett", "Saul Johansen").
friend_("Monika Crim", "Jewel Messenger").
friend_("Monika Crim", "Saul Johansen").
friend_("Monika Crim", "Scotty Messenger").
friend_("Octavio Ybarra", "Rodrick Johansen").
friend_("Octavio Ybarra", "Selena Messenger").
friend_("Perla Dorsett", "Rosella Ochs").
friend_("Perla Dorsett", "Zachery Ybarra").
friend_("Perla Dorsett", "Georgette Messenger").
friend_("Perla Dorsett", "Linwood Messenger").
friend_("Perla Dorsett", "Maira Witt").
friend_("Perla Dorsett", "Nathan Witt").
friend_("Perla Dorsett", "Warren Messenger").
friend_("Randall Shattuck", "Von Dorsett").
friend_("Randall Shattuck", "Boyd Messenger").
friend_("Randall Shattuck", "Cleveland Johansen").
friend_("Randall Shattuck", "Lurline Messenger").
friend_("Rosella Ochs", "Trisha Crim").
friend_("Rosella Ochs", "Geoffrey Driskell").
friend_("Rosella Ochs", "Jewel Messenger").
friend_("Rosella Ochs", "Scotty Messenger").
friend_("Ruby Ybarra", "Scotty Messenger").
friend_("Shawna Ochs", "Alejandra Driskell").
friend_("Shawna Ochs", "Lurline Messenger").
friend_("Violet Shattuck", "Von Dorsett").
friend_("Violet Shattuck", "Jason Messenger").
friend_("Violet Shattuck", "Saul Johansen").
friend_("Von Dorsett", "Georgette Messenger").
friend_("Von Dorsett", "Linwood Messenger").
friend_("Boyd Messenger", "Hank Messenger").
friend_("Boyd Messenger", "Selena Messenger").
friend_("Boyd Messenger", "Warren Messenger").
friend_("Eric Hoagland", "Saul Johansen").
friend_("Georgette Messenger", "Selena Messenger").
friend_("Hank Messenger", "Jewel Messenger").
friend_("Jason Messenger", "Jewel Messenger").
friend_("Lara Driskell", "Linwood Messenger").
friend_("Lurline Messenger", "Selena Messenger").
friend_("Lyndia Hoagland", "Saul Johansen").
friend_("Minerva Johansen", "Rodrick Johansen").
friend_("Nathan Witt", "Rosalee Johansen").
friend_("Rosalee Johansen", "Selena Messenger").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("international aid worker").
attribute("dog sport").
attribute("multimedia programmer").
attribute("karting").
attribute("marine scientist").
attribute("linguistics").
attribute("horticultural consultant").
attribute("kabaddi").
attribute("patent attorney").
attribute("fingerprint collecting").
attribute("research scientist").
attribute("go").
attribute("environmental education officer").
attribute("stone collecting").
attribute("orthoptist").
attribute("physics").
attribute("retail manager").
attribute("model united nations").
attribute("television camera operator").
attribute("social studies").
attribute("development worker").
attribute("learning").
attribute("management consultant").
attribute("antiquities").
attribute("chief operating officer").
attribute("reading").
attribute("analytical chemist").
attribute("tourism").
attribute("commercial surveyor").
attribute("seashell collecting").
attribute("cabin crew").
attribute("shortwave listening").
attribute("probation officer").
attribute("notaphily").
attribute("call centre manager").
attribute("social studies").
attribute("housing manager").
attribute("photography").
attribute("forensic scientist").
attribute("video gaming").
attribute("contractor").
attribute("sports science").
attribute("research scientist").
attribute("ant-keeping").
attribute("media planner").
attribute("crystals").
attribute("lawyer").
attribute("basketball").
attribute("waste management officer").
attribute("people-watching").
attribute("airline pilot").
attribute("sea glass collecting").
attribute("horticultural therapist").
attribute("vinyl records").
attribute("financial adviser").
attribute("tour skating").
attribute("artist").
attribute("fossil hunting").
attribute("operational investment banker").
attribute("flower collecting and pressing").
attribute("management consultant").
attribute("beach volleyball").
attribute("risk analyst").
attribute("speedcubing").
attribute("scientific laboratory technician").
attribute("rock balancing").
attribute("haematologist").
attribute("sea glass collecting").
attribute("chartered legal executive").
attribute("transit map collecting").
attribute("retail merchandiser").
attribute("research").
attribute("police officer").
attribute("element collecting").
attribute("clothing technologist").
attribute("coin collecting").
attribute("civil service administrator").
attribute("animal fancy").
attribute("visual merchandiser").
attribute("tea bag collecting").
attribute("interpreter").
attribute("unicycling").
attribute("network engineer").
attribute("video game collecting").
attribute("site engineer").
attribute("publishing").
attribute("secondary school teacher").
attribute("darts").
attribute("air traffic controller").
attribute("benchmarking").
attribute("medical technical officer").
attribute("whale watching").
attribute("cartographer").
attribute("people-watching").
attribute("economist").
attribute("horseback riding").
attribute("midwife").
attribute("dancing").
attribute("trade union research officer").
attribute("pinball").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Austin Crim", person).
type("Cristal Showers", person).
type("Darrel Showers", person).
type("Elvin Ybarra", person).
type("Francis Tooley", person).
type("Gale Ybarra", person).
type("Glenda Ochs", person).
type("Hoa Tooley", person).
type("Hosea Ochs", person).
type("Ivan Ochs", person).
type("Katherine Showers", person).
type("Kisha Ybarra", person).
type("Larue Dorsett", person).
type("Monika Crim", person).
type("Octavio Ybarra", person).
type("Perla Dorsett", person).
type("Randall Shattuck", person).
type("Rosella Ochs", person).
type("Ruby Ybarra", person).
type("Shawna Ochs", person).
type("Stan Shattuck", person).
type("Trisha Crim", person).
type("Violet Shattuck", person).
type("Von Dorsett", person).
type("Zachery Ybarra", person).
type("Alejandra Driskell", person).
type("Boyd Messenger", person).
type("Cleveland Johansen", person).
type("Eric Hoagland", person).
type("Geoffrey Driskell", person).
type("Georgette Messenger", person).
type("Hank Messenger", person).
type("Jackie Messenger", person).
type("Jason Messenger", person).
type("Jewel Messenger", person).
type("Lara Driskell", person).
type("Linwood Messenger", person).
type("Lurline Messenger", person).
type("Lyndia Hoagland", person).
type("Maira Witt", person).
type("Minerva Johansen", person).
type("Nathan Witt", person).
type("Rodrick Johansen", person).
type("Rosalee Johansen", person).
type("Sara Messenger", person).
type("Saul Johansen", person).
type("Scotty Messenger", person).
type("Selena Messenger", person).
type("Terence Hoagland", person).
type("Warren Messenger", person).

:- dynamic dob/2.

dob("Austin Crim", "0300-09-21").
dob("Cristal Showers", "0279-12-11").
dob("Darrel Showers", "0281-10-08").
dob("Elvin Ybarra", "0251-04-10").
dob("Francis Tooley", "0194-08-06").
dob("Gale Ybarra", "0281-01-20").
dob("Glenda Ochs", "0277-04-23").
dob("Hoa Tooley", "0194-02-19").
dob("Hosea Ochs", "0257-02-15").
dob("Ivan Ochs", "0277-01-07").
dob("Katherine Showers", "0310-01-24").
dob("Kisha Ybarra", "0252-01-21").
dob("Larue Dorsett", "0302-02-26").
dob("Monika Crim", "0300-04-03").
dob("Octavio Ybarra", "0280-02-15").
dob("Perla Dorsett", "0274-10-13").
dob("Randall Shattuck", "0310-07-01").
dob("Rosella Ochs", "0304-06-03").
dob("Ruby Ybarra", "0223-08-17").
dob("Shawna Ochs", "0254-12-13").
dob("Stan Shattuck", "0330-07-31").
dob("Trisha Crim", "0329-05-11").
dob("Violet Shattuck", "0307-11-04").
dob("Von Dorsett", "0274-08-14").
dob("Zachery Ybarra", "0225-08-02").
dob("Alejandra Driskell", "0249-07-04").
dob("Boyd Messenger", "0264-02-01").
dob("Cleveland Johansen", "0239-09-12").
dob("Eric Hoagland", "0327-02-23").
dob("Geoffrey Driskell", "0222-10-05").
dob("Georgette Messenger", "0264-02-15").
dob("Hank Messenger", "0296-03-04").
dob("Jackie Messenger", "0262-03-10").
dob("Jason Messenger", "0265-01-24").
dob("Jewel Messenger", "0294-05-29").
dob("Lara Driskell", "0220-02-26").
dob("Linwood Messenger", "0293-05-16").
dob("Lurline Messenger", "0320-11-07").
dob("Lyndia Hoagland", "0291-04-10").
dob("Maira Witt", "0180-02-07").
dob("Minerva Johansen", "0208-07-26").
dob("Nathan Witt", "0181-10-16").
dob("Rodrick Johansen", "0268-10-07").
dob("Rosalee Johansen", "0242-04-20").
dob("Sara Messenger", "0267-03-07").
dob("Saul Johansen", "0208-02-13").
dob("Scotty Messenger", "0289-07-08").
dob("Selena Messenger", "0235-04-08").
dob("Terence Hoagland", "0291-05-22").
dob("Warren Messenger", "0237-04-02").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Austin Crim", "international aid worker").
job("Cristal Showers", "multimedia programmer").
job("Darrel Showers", "marine scientist").
job("Elvin Ybarra", "horticultural consultant").
job("Francis Tooley", "patent attorney").
job("Gale Ybarra", "research scientist").
job("Glenda Ochs", "environmental education officer").
job("Hoa Tooley", "orthoptist").
job("Hosea Ochs", "retail manager").
job("Ivan Ochs", "television camera operator").
job("Katherine Showers", "development worker").
job("Kisha Ybarra", "management consultant").
job("Larue Dorsett", "chief operating officer").
job("Monika Crim", "analytical chemist").
job("Octavio Ybarra", "commercial surveyor").
job("Perla Dorsett", "cabin crew").
job("Randall Shattuck", "probation officer").
job("Rosella Ochs", "call centre manager").
job("Ruby Ybarra", "housing manager").
job("Shawna Ochs", "forensic scientist").
job("Stan Shattuck", "contractor").
job("Trisha Crim", "research scientist").
job("Violet Shattuck", "media planner").
job("Von Dorsett", "lawyer").
job("Zachery Ybarra", "waste management officer").
job("Alejandra Driskell", "airline pilot").
job("Boyd Messenger", "horticultural therapist").
job("Cleveland Johansen", "financial adviser").
job("Eric Hoagland", "artist").
job("Geoffrey Driskell", "operational investment banker").
job("Georgette Messenger", "management consultant").
job("Hank Messenger", "risk analyst").
job("Jackie Messenger", "scientific laboratory technician").
job("Jason Messenger", "haematologist").
job("Jewel Messenger", "chartered legal executive").
job("Lara Driskell", "retail merchandiser").
job("Linwood Messenger", "police officer").
job("Lurline Messenger", "clothing technologist").
job("Lyndia Hoagland", "civil service administrator").
job("Maira Witt", "visual merchandiser").
job("Minerva Johansen", "interpreter").
job("Nathan Witt", "network engineer").
job("Rodrick Johansen", "site engineer").
job("Rosalee Johansen", "secondary school teacher").
job("Sara Messenger", "air traffic controller").
job("Saul Johansen", "medical technical officer").
job("Scotty Messenger", "cartographer").
job("Selena Messenger", "economist").
job("Terence Hoagland", "midwife").
job("Warren Messenger", "trade union research officer").

:- dynamic expand_query/4.
:- multifile expand_query/4.


grandfather(X, Y) :-
    grandparent(X, Y),
    male(Y).

:- dynamic save_all_clauses_to_file/1.

save_all_clauses_to_file(A) :-
    open(A, write, B),
    set_output(B),
    listing,
    close(B).

grandmother(X, Y) :-
    grandparent(X, Y),
    female(Y).

:- thread_local thread_message_hook/3.
:- dynamic thread_message_hook/3.
:- volatile thread_message_hook/3.

%   No thread has clauses for thread_message_hook/3

:- dynamic hobby/2.

hobby("Austin Crim", "dog sport").
hobby("Cristal Showers", "karting").
hobby("Darrel Showers", "linguistics").
hobby("Elvin Ybarra", "kabaddi").
hobby("Francis Tooley", "fingerprint collecting").
hobby("Gale Ybarra", "go").
hobby("Glenda Ochs", "stone collecting").
hobby("Hoa Tooley", "physics").
hobby("Hosea Ochs", "model united nations").
hobby("Ivan Ochs", "social studies").
hobby("Katherine Showers", "learning").
hobby("Kisha Ybarra", "antiquities").
hobby("Larue Dorsett", "reading").
hobby("Monika Crim", "tourism").
hobby("Octavio Ybarra", "seashell collecting").
hobby("Perla Dorsett", "shortwave listening").
hobby("Randall Shattuck", "notaphily").
hobby("Rosella Ochs", "social studies").
hobby("Ruby Ybarra", "photography").
hobby("Shawna Ochs", "video gaming").
hobby("Stan Shattuck", "sports science").
hobby("Trisha Crim", "ant-keeping").
hobby("Violet Shattuck", "crystals").
hobby("Von Dorsett", "basketball").
hobby("Zachery Ybarra", "people-watching").
hobby("Alejandra Driskell", "sea glass collecting").
hobby("Boyd Messenger", "vinyl records").
hobby("Cleveland Johansen", "tour skating").
hobby("Eric Hoagland", "fossil hunting").
hobby("Geoffrey Driskell", "flower collecting and pressing").
hobby("Georgette Messenger", "beach volleyball").
hobby("Hank Messenger", "speedcubing").
hobby("Jackie Messenger", "rock balancing").
hobby("Jason Messenger", "sea glass collecting").
hobby("Jewel Messenger", "transit map collecting").
hobby("Lara Driskell", "research").
hobby("Linwood Messenger", "element collecting").
hobby("Lurline Messenger", "coin collecting").
hobby("Lyndia Hoagland", "animal fancy").
hobby("Maira Witt", "tea bag collecting").
hobby("Minerva Johansen", "unicycling").
hobby("Nathan Witt", "video game collecting").
hobby("Rodrick Johansen", "publishing").
hobby("Rosalee Johansen", "darts").
hobby("Sara Messenger", "benchmarking").
hobby("Saul Johansen", "whale watching").
hobby("Scotty Messenger", "people-watching").
hobby("Selena Messenger", "horseback riding").
hobby("Terence Hoagland", "dancing").
hobby("Warren Messenger", "pinball").

grandparent(X, Y) :-
    parent(X, Z),
    parent(Z, Y).

nephew(X, Y) :-
    sibling(X, A),
    son(A, Y).

niece(X, Y) :-
    sibling(X, A),
    daughter(A, Y).

:- dynamic library_directory/1.
:- multifile library_directory/1.


:- dynamic prolog_file_type/2.
:- multifile prolog_file_type/2.

prolog_file_type(pl, prolog).
prolog_file_type(prolog, prolog).
prolog_file_type(qlf, prolog).
prolog_file_type(pl, source).
prolog_file_type(prolog, source).
prolog_file_type(qlf, qlf).
prolog_file_type(A, executable) :-
    system:current_prolog_flag(shared_object_extension, A).
prolog_file_type(dylib, executable) :-
    system:current_prolog_flag(apple, true).

husband(X, Y) :-
    married(X, Y),
    male(Y).

wife(X, Y) :-
    married(X, Y),
    female(Y).
