
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

parent("Cecil Cornwell", "Jefferson Cornwell").
parent("Cecil Cornwell", "Leesa Cornwell").
parent("Dallas Kline", "Addie Kline").
parent("Dallas Kline", "Lonny Kline").
parent("Deena Kline", "Addie Kline").
parent("Deena Kline", "Lonny Kline").
parent("Erik Cornwell", "Jefferson Cornwell").
parent("Erik Cornwell", "Leesa Cornwell").
parent("Freddie Kline", "Jeannine Kline").
parent("Freddie Kline", "Kenton Kline").
parent("Golda Kline", "Jeanette Kline").
parent("Golda Kline", "Tyron Kline").
parent("Jamal Cornwell", "Cecil Cornwell").
parent("Jamal Cornwell", "Sadye Cornwell").
parent("Jeanette Kline", "Jenny Colter").
parent("Jeanette Kline", "Sebastian Colter").
parent("Kenton Kline", "Addie Kline").
parent("Kenton Kline", "Lonny Kline").
parent("Leesa Cornwell", "Leroy Bidwell").
parent("Leesa Cornwell", "Lucretia Bidwell").
parent("Levi Cornwell", "Jefferson Cornwell").
parent("Levi Cornwell", "Leesa Cornwell").
parent("Lucretia Bidwell", "Jeanette Kline").
parent("Lucretia Bidwell", "Tyron Kline").
parent("Quincy Cornwell", "Cecil Cornwell").
parent("Quincy Cornwell", "Sadye Cornwell").
parent("Roxy Cornwell", "Jefferson Cornwell").
parent("Roxy Cornwell", "Leesa Cornwell").
parent("Tena Bidwell", "Leroy Bidwell").
parent("Tena Bidwell", "Lucretia Bidwell").
parent("Terrell Cornwell", "Cecil Cornwell").
parent("Terrell Cornwell", "Sadye Cornwell").
parent("Tyron Kline", "Addie Kline").
parent("Tyron Kline", "Lonny Kline").
parent("Abdul West", "Ora West").
parent("Abdul West", "Ramon West").
parent("Hyun West", "Geri West").
parent("Hyun West", "Ted West").
parent("Johnetta West", "Hattie West").
parent("Johnetta West", "Stuart West").
parent("Kristopher West", "Isabella West").
parent("Kristopher West", "Oliver West").
parent("Marguerite Mingo", "Ella Mingo").
parent("Marguerite Mingo", "Maximo Mingo").
parent("Matilda West", "Gregory Yazzie").
parent("Matilda West", "Thelma Yazzie").
parent("Morgan West", "Ora West").
parent("Morgan West", "Ramon West").
parent("Oliver West", "Johnna West").
parent("Oliver West", "Logan West").
parent("Ora West", "Ella Mingo").
parent("Ora West", "Maximo Mingo").
parent("Ramon West", "Kristopher West").
parent("Ramon West", "Matilda West").
parent("Randal West", "Geri West").
parent("Randal West", "Ted West").
parent("Stuart West", "Kristopher West").
parent("Stuart West", "Matilda West").
parent("Ted West", "Hattie West").
parent("Ted West", "Stuart West").
parent("Thelma Yazzie", "Audra Juarez").
parent("Thelma Yazzie", "Stanford Juarez").
parent("Vern Yazzie", "Gregory Yazzie").
parent("Vern Yazzie", "Thelma Yazzie").

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

gender("Addie Kline", "female").
gender("Cecil Cornwell", "male").
gender("Dallas Kline", "female").
gender("Deena Kline", "female").
gender("Erik Cornwell", "male").
gender("Freddie Kline", "male").
gender("Golda Kline", "female").
gender("Jamal Cornwell", "male").
gender("Jeanette Kline", "female").
gender("Jeannine Kline", "female").
gender("Jefferson Cornwell", "male").
gender("Jenny Colter", "female").
gender("Kenton Kline", "male").
gender("Leesa Cornwell", "female").
gender("Leroy Bidwell", "male").
gender("Levi Cornwell", "male").
gender("Lonny Kline", "male").
gender("Lucretia Bidwell", "female").
gender("Quincy Cornwell", "male").
gender("Roxy Cornwell", "female").
gender("Sadye Cornwell", "female").
gender("Sebastian Colter", "male").
gender("Tena Bidwell", "female").
gender("Terrell Cornwell", "male").
gender("Tyron Kline", "male").
gender("Abdul West", "male").
gender("Audra Juarez", "female").
gender("Ella Mingo", "female").
gender("Geri West", "female").
gender("Gregory Yazzie", "male").
gender("Hattie West", "female").
gender("Hyun West", "female").
gender("Isabella West", "female").
gender("Johnetta West", "female").
gender("Johnna West", "female").
gender("Kristopher West", "male").
gender("Logan West", "male").
gender("Marguerite Mingo", "female").
gender("Matilda West", "female").
gender("Maximo Mingo", "male").
gender("Morgan West", "female").
gender("Oliver West", "male").
gender("Ora West", "female").
gender("Ramon West", "male").
gender("Randal West", "male").
gender("Stanford Juarez", "male").
gender("Stuart West", "male").
gender("Ted West", "male").
gender("Thelma Yazzie", "female").
gender("Vern Yazzie", "male").

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

friend_("Addie Kline", "Leroy Bidwell").
friend_("Addie Kline", "Logan West").
friend_("Addie Kline", "Maximo Mingo").
friend_("Addie Kline", "Stanford Juarez").
friend_("Cecil Cornwell", "Freddie Kline").
friend_("Cecil Cornwell", "Leesa Cornwell").
friend_("Cecil Cornwell", "Abdul West").
friend_("Cecil Cornwell", "Geri West").
friend_("Cecil Cornwell", "Marguerite Mingo").
friend_("Dallas Kline", "Kenton Kline").
friend_("Dallas Kline", "Logan West").
friend_("Deena Kline", "Terrell Cornwell").
friend_("Deena Kline", "Logan West").
friend_("Deena Kline", "Marguerite Mingo").
friend_("Erik Cornwell", "Golda Kline").
friend_("Erik Cornwell", "Jeannine Kline").
friend_("Freddie Kline", "Jefferson Cornwell").
friend_("Freddie Kline", "Jenny Colter").
friend_("Freddie Kline", "Stanford Juarez").
friend_("Golda Kline", "Jenny Colter").
friend_("Golda Kline", "Leroy Bidwell").
friend_("Golda Kline", "Lucretia Bidwell").
friend_("Golda Kline", "Geri West").
friend_("Jamal Cornwell", "Abdul West").
friend_("Jeanette Kline", "Morgan West").
friend_("Jeannine Kline", "Sebastian Colter").
friend_("Jeannine Kline", "Tena Bidwell").
friend_("Jefferson Cornwell", "Quincy Cornwell").
friend_("Jefferson Cornwell", "Sadye Cornwell").
friend_("Jefferson Cornwell", "Tena Bidwell").
friend_("Jefferson Cornwell", "Kristopher West").
friend_("Jefferson Cornwell", "Stuart West").
friend_("Jenny Colter", "Leesa Cornwell").
friend_("Jenny Colter", "Sadye Cornwell").
friend_("Jenny Colter", "Sebastian Colter").
friend_("Jenny Colter", "Isabella West").
friend_("Kenton Kline", "Ted West").
friend_("Leesa Cornwell", "Leroy Bidwell").
friend_("Leesa Cornwell", "Johnetta West").
friend_("Leesa Cornwell", "Kristopher West").
friend_("Leesa Cornwell", "Logan West").
friend_("Leesa Cornwell", "Marguerite Mingo").
friend_("Leroy Bidwell", "Hyun West").
friend_("Levi Cornwell", "Oliver West").
friend_("Lonny Kline", "Sadye Cornwell").
friend_("Lonny Kline", "Sebastian Colter").
friend_("Lonny Kline", "Geri West").
friend_("Lonny Kline", "Gregory Yazzie").
friend_("Lonny Kline", "Johnna West").
friend_("Lucretia Bidwell", "Tyron Kline").
friend_("Lucretia Bidwell", "Hyun West").
friend_("Lucretia Bidwell", "Johnetta West").
friend_("Lucretia Bidwell", "Morgan West").
friend_("Lucretia Bidwell", "Stanford Juarez").
friend_("Roxy Cornwell", "Tena Bidwell").
friend_("Sadye Cornwell", "Tena Bidwell").
friend_("Sadye Cornwell", "Geri West").
friend_("Sadye Cornwell", "Hyun West").
friend_("Sadye Cornwell", "Johnna West").
friend_("Sadye Cornwell", "Maximo Mingo").
friend_("Sebastian Colter", "Hattie West").
friend_("Tena Bidwell", "Audra Juarez").
friend_("Abdul West", "Kristopher West").
friend_("Abdul West", "Logan West").
friend_("Abdul West", "Oliver West").
friend_("Audra Juarez", "Gregory Yazzie").
friend_("Audra Juarez", "Oliver West").
friend_("Audra Juarez", "Ted West").
friend_("Ella Mingo", "Johnna West").
friend_("Ella Mingo", "Maximo Mingo").
friend_("Geri West", "Randal West").
friend_("Gregory Yazzie", "Vern Yazzie").
friend_("Hattie West", "Stuart West").
friend_("Hattie West", "Thelma Yazzie").
friend_("Hyun West", "Morgan West").
friend_("Hyun West", "Stuart West").
friend_("Johnna West", "Morgan West").
friend_("Johnna West", "Ted West").
friend_("Kristopher West", "Morgan West").
friend_("Kristopher West", "Vern Yazzie").
friend_("Ramon West", "Ted West").
friend_("Randal West", "Stanford Juarez").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("senior tax professional").
attribute("book folding").
attribute("location manager").
attribute("fossil hunting").
attribute("colour technologist").
attribute("gymnastics").
attribute("clinical cytogeneticist").
attribute("butterfly watching").
attribute("applications developer").
attribute("geocaching").
attribute("trade mark attorney").
attribute("reading").
attribute("advertising copywriter").
attribute("element collecting").
attribute("company secretary").
attribute("trapshooting").
attribute("arts development officer").
attribute("shortwave listening").
attribute("actuary").
attribute("model united nations").
attribute("structural engineer").
attribute("dodgeball").
attribute("clinical embryologist").
attribute("ant farming").
attribute("scientific laboratory technician").
attribute("rock balancing").
attribute("building control surveyor").
attribute("tea bag collecting").
attribute("bookseller").
attribute("hobby horsing").
attribute("horticulturist").
attribute("aerospace").
attribute("water engineer").
attribute("magnet fishing").
attribute("paediatric nurse").
attribute("mountain biking").
attribute("building services engineer").
attribute("research").
attribute("physicist").
attribute("auto audiophilia").
attribute("database administrator").
attribute("weightlifting").
attribute("sports administrator").
attribute("horsemanship").
attribute("tree surgeon").
attribute("art collecting").
attribute("teacher").
attribute("sea glass collecting").
attribute("television producer").
attribute("go").
attribute("physicist").
attribute("reading").
attribute("scientist").
attribute("myrmecology").
attribute("education officer").
attribute("biology").
attribute("TEFL teacher").
attribute("tennis").
attribute("tree surgeon").
attribute("coin collecting").
attribute("lobbyist").
attribute("rugby league football").
attribute("clinical molecular geneticist").
attribute("satellite watching").
attribute("animator").
attribute("darts").
attribute("hydrographic surveyor").
attribute("jujitsu").
attribute("physiotherapist").
attribute("jurisprudential").
attribute("health and safety inspector").
attribute("ant farming").
attribute("clothing technologist").
attribute("psychology").
attribute("geologist").
attribute("benchmarking").
attribute("field trials officer").
attribute("science and technology studies").
attribute("herbalist").
attribute("mineral collecting").
attribute("commissioning editor").
attribute("digital hoarding").
attribute("paediatric nurse").
attribute("fishkeeping").
attribute("animal nutritionist").
attribute("dolls").
attribute("stage manager").
attribute("whale watching").
attribute("retail manager").
attribute("benchmarking").
attribute("public relations account executive").
attribute("volunteering").
attribute("licensed conveyancer").
attribute("leaves").
attribute("police officer").
attribute("aircraft spotting").
attribute("editorial assistant").
attribute("geocaching").
attribute("clinical scientist").
attribute("vacation").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Addie Kline", person).
type("Cecil Cornwell", person).
type("Dallas Kline", person).
type("Deena Kline", person).
type("Erik Cornwell", person).
type("Freddie Kline", person).
type("Golda Kline", person).
type("Jamal Cornwell", person).
type("Jeanette Kline", person).
type("Jeannine Kline", person).
type("Jefferson Cornwell", person).
type("Jenny Colter", person).
type("Kenton Kline", person).
type("Leesa Cornwell", person).
type("Leroy Bidwell", person).
type("Levi Cornwell", person).
type("Lonny Kline", person).
type("Lucretia Bidwell", person).
type("Quincy Cornwell", person).
type("Roxy Cornwell", person).
type("Sadye Cornwell", person).
type("Sebastian Colter", person).
type("Tena Bidwell", person).
type("Terrell Cornwell", person).
type("Tyron Kline", person).
type("Abdul West", person).
type("Audra Juarez", person).
type("Ella Mingo", person).
type("Geri West", person).
type("Gregory Yazzie", person).
type("Hattie West", person).
type("Hyun West", person).
type("Isabella West", person).
type("Johnetta West", person).
type("Johnna West", person).
type("Kristopher West", person).
type("Logan West", person).
type("Marguerite Mingo", person).
type("Matilda West", person).
type("Maximo Mingo", person).
type("Morgan West", person).
type("Oliver West", person).
type("Ora West", person).
type("Ramon West", person).
type("Randal West", person).
type("Stanford Juarez", person).
type("Stuart West", person).
type("Ted West", person).
type("Thelma Yazzie", person).
type("Vern Yazzie", person).

:- dynamic dob/2.

dob("Addie Kline", "0174-10-05").
dob("Cecil Cornwell", "0288-08-23").
dob("Dallas Kline", "0199-11-11").
dob("Deena Kline", "0201-10-01").
dob("Erik Cornwell", "0288-09-01").
dob("Freddie Kline", "0227-10-08").
dob("Golda Kline", "0232-05-26").
dob("Jamal Cornwell", "0318-06-20").
dob("Jeanette Kline", "0202-05-06").
dob("Jeannine Kline", "0202-03-06").
dob("Jefferson Cornwell", "0262-09-12").
dob("Jenny Colter", "0170-10-11").
dob("Kenton Kline", "0202-12-20").
dob("Leesa Cornwell", "0261-09-15").
dob("Leroy Bidwell", "0229-12-02").
dob("Levi Cornwell", "0289-03-01").
dob("Lonny Kline", "0172-07-20").
dob("Lucretia Bidwell", "0228-11-08").
dob("Quincy Cornwell", "0317-03-13").
dob("Roxy Cornwell", "0288-09-01").
dob("Sadye Cornwell", "0289-04-07").
dob("Sebastian Colter", "0173-07-10").
dob("Tena Bidwell", "0254-03-22").
dob("Terrell Cornwell", "0315-07-07").
dob("Tyron Kline", "0202-12-20").
dob("Abdul West", "0301-04-11").
dob("Audra Juarez", "0193-07-11").
dob("Ella Mingo", "0245-11-17").
dob("Geri West", "0297-09-28").
dob("Gregory Yazzie", "0212-04-26").
dob("Hattie West", "0268-04-23").
dob("Hyun West", "0327-08-26").
dob("Isabella West", "0211-04-10").
dob("Johnetta West", "0293-10-06").
dob("Johnna West", "0185-09-27").
dob("Kristopher West", "0244-12-13").
dob("Logan West", "0185-08-23").
dob("Marguerite Mingo", "0278-08-06").
dob("Matilda West", "0238-07-02").
dob("Maximo Mingo", "0244-08-06").
dob("Morgan West", "0300-03-08").
dob("Oliver West", "0214-11-01").
dob("Ora West", "0270-06-03").
dob("Ramon West", "0273-11-17").
dob("Randal West", "0321-02-19").
dob("Stanford Juarez", "0193-09-03").
dob("Stuart West", "0270-12-18").
dob("Ted West", "0299-05-16").
dob("Thelma Yazzie", "0213-04-08").
dob("Vern Yazzie", "0237-07-15").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Addie Kline", "senior tax professional").
job("Cecil Cornwell", "location manager").
job("Dallas Kline", "colour technologist").
job("Deena Kline", "clinical cytogeneticist").
job("Erik Cornwell", "applications developer").
job("Freddie Kline", "trade mark attorney").
job("Golda Kline", "advertising copywriter").
job("Jamal Cornwell", "company secretary").
job("Jeanette Kline", "arts development officer").
job("Jeannine Kline", "actuary").
job("Jefferson Cornwell", "structural engineer").
job("Jenny Colter", "clinical embryologist").
job("Kenton Kline", "scientific laboratory technician").
job("Leesa Cornwell", "building control surveyor").
job("Leroy Bidwell", "bookseller").
job("Levi Cornwell", "horticulturist").
job("Lonny Kline", "water engineer").
job("Lucretia Bidwell", "paediatric nurse").
job("Quincy Cornwell", "building services engineer").
job("Roxy Cornwell", "physicist").
job("Sadye Cornwell", "database administrator").
job("Sebastian Colter", "sports administrator").
job("Tena Bidwell", "tree surgeon").
job("Terrell Cornwell", "teacher").
job("Tyron Kline", "television producer").
job("Abdul West", "physicist").
job("Audra Juarez", "scientist").
job("Ella Mingo", "education officer").
job("Geri West", "TEFL teacher").
job("Gregory Yazzie", "tree surgeon").
job("Hattie West", "lobbyist").
job("Hyun West", "clinical molecular geneticist").
job("Isabella West", "animator").
job("Johnetta West", "hydrographic surveyor").
job("Johnna West", "physiotherapist").
job("Kristopher West", "health and safety inspector").
job("Logan West", "clothing technologist").
job("Marguerite Mingo", "geologist").
job("Matilda West", "field trials officer").
job("Maximo Mingo", "herbalist").
job("Morgan West", "commissioning editor").
job("Oliver West", "paediatric nurse").
job("Ora West", "animal nutritionist").
job("Ramon West", "stage manager").
job("Randal West", "retail manager").
job("Stanford Juarez", "public relations account executive").
job("Stuart West", "licensed conveyancer").
job("Ted West", "police officer").
job("Thelma Yazzie", "editorial assistant").
job("Vern Yazzie", "clinical scientist").

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

hobby("Addie Kline", "book folding").
hobby("Cecil Cornwell", "fossil hunting").
hobby("Dallas Kline", "gymnastics").
hobby("Deena Kline", "butterfly watching").
hobby("Erik Cornwell", "geocaching").
hobby("Freddie Kline", "reading").
hobby("Golda Kline", "element collecting").
hobby("Jamal Cornwell", "trapshooting").
hobby("Jeanette Kline", "shortwave listening").
hobby("Jeannine Kline", "model united nations").
hobby("Jefferson Cornwell", "dodgeball").
hobby("Jenny Colter", "ant farming").
hobby("Kenton Kline", "rock balancing").
hobby("Leesa Cornwell", "tea bag collecting").
hobby("Leroy Bidwell", "hobby horsing").
hobby("Levi Cornwell", "aerospace").
hobby("Lonny Kline", "magnet fishing").
hobby("Lucretia Bidwell", "mountain biking").
hobby("Quincy Cornwell", "research").
hobby("Roxy Cornwell", "auto audiophilia").
hobby("Sadye Cornwell", "weightlifting").
hobby("Sebastian Colter", "horsemanship").
hobby("Tena Bidwell", "art collecting").
hobby("Terrell Cornwell", "sea glass collecting").
hobby("Tyron Kline", "go").
hobby("Abdul West", "reading").
hobby("Audra Juarez", "myrmecology").
hobby("Ella Mingo", "biology").
hobby("Geri West", "tennis").
hobby("Gregory Yazzie", "coin collecting").
hobby("Hattie West", "rugby league football").
hobby("Hyun West", "satellite watching").
hobby("Isabella West", "darts").
hobby("Johnetta West", "jujitsu").
hobby("Johnna West", "jurisprudential").
hobby("Kristopher West", "ant farming").
hobby("Logan West", "psychology").
hobby("Marguerite Mingo", "benchmarking").
hobby("Matilda West", "science and technology studies").
hobby("Maximo Mingo", "mineral collecting").
hobby("Morgan West", "digital hoarding").
hobby("Oliver West", "fishkeeping").
hobby("Ora West", "dolls").
hobby("Ramon West", "whale watching").
hobby("Randal West", "benchmarking").
hobby("Stanford Juarez", "volunteering").
hobby("Stuart West", "leaves").
hobby("Ted West", "aircraft spotting").
hobby("Thelma Yazzie", "geocaching").
hobby("Vern Yazzie", "vacation").

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
