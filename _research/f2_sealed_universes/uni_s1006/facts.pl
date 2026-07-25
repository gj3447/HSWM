
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

parent("Almeta Lanza", "Manuel Matheson").
parent("Almeta Lanza", "Sara Matheson").
parent("Antonia Lanza", "Almeta Lanza").
parent("Antonia Lanza", "Hiram Lanza").
parent("Bobby Kingery", "Ivette Kingery").
parent("Bobby Kingery", "Jimmie Kingery").
parent("Ellen Munguia", "Tamala Munguia").
parent("Ellen Munguia", "Timmy Munguia").
parent("Harold Grayson", "Lindsey Grayson").
parent("Harold Grayson", "Maurice Grayson").
parent("Ivette Kingery", "Almeta Lanza").
parent("Ivette Kingery", "Hiram Lanza").
parent("Johnetta Matheson", "Tamala Munguia").
parent("Johnetta Matheson", "Timmy Munguia").
parent("Kerry Grayson", "Manuel Matheson").
parent("Kerry Grayson", "Sara Matheson").
parent("Lane Mcglynn", "Adam Mcglynn").
parent("Lane Mcglynn", "Shaina Mcglynn").
parent("Magdalene Matheson", "Manuel Matheson").
parent("Magdalene Matheson", "Sara Matheson").
parent("Manuel Matheson", "Benito Matheson").
parent("Manuel Matheson", "Johnetta Matheson").
parent("Mariann Grayson", "Harold Grayson").
parent("Mariann Grayson", "Kerry Grayson").
parent("Michell Kingery", "Ivette Kingery").
parent("Michell Kingery", "Jimmie Kingery").
parent("Rolando Matheson", "Benito Matheson").
parent("Rolando Matheson", "Johnetta Matheson").
parent("Samual Grayson", "Harold Grayson").
parent("Samual Grayson", "Kerry Grayson").
parent("Shaina Mcglynn", "Benito Matheson").
parent("Shaina Mcglynn", "Johnetta Matheson").
parent("Barry Mcnamee", "Bo Mcnamee").
parent("Barry Mcnamee", "Karrie Mcnamee").
parent("Bo Mcnamee", "Everett Mcnamee").
parent("Bo Mcnamee", "Jacquelyn Mcnamee").
parent("Carmon Bledsoe", "Alberto Vogel").
parent("Carmon Bledsoe", "Krystle Vogel").
parent("Charley Mcnamee", "Bo Mcnamee").
parent("Charley Mcnamee", "Karrie Mcnamee").
parent("Deidre Fitzpatrick", "Carmon Bledsoe").
parent("Deidre Fitzpatrick", "Eddy Bledsoe").
parent("Eddy Bledsoe", "Lona Bledsoe").
parent("Eddy Bledsoe", "Philip Bledsoe").
parent("Emmett Bledsoe", "Carmon Bledsoe").
parent("Emmett Bledsoe", "Eddy Bledsoe").
parent("Jacquelyn Mcnamee", "Alberto Vogel").
parent("Jacquelyn Mcnamee", "Krystle Vogel").
parent("Kieth Mcnamee", "Charley Mcnamee").
parent("Kieth Mcnamee", "Pauline Mcnamee").
parent("Lanny Mcnamee", "Bo Mcnamee").
parent("Lanny Mcnamee", "Karrie Mcnamee").
parent("Philip Bledsoe", "Joe Bledsoe").
parent("Philip Bledsoe", "Rasheeda Bledsoe").
parent("Reyes Mcnamee", "Lanny Mcnamee").
parent("Reyes Mcnamee", "Myrl Mcnamee").
parent("Shaunte Mcnamee", "Barry Mcnamee").
parent("Shaunte Mcnamee", "Colleen Mcnamee").
parent("Tad Fitzpatrick", "Deidre Fitzpatrick").
parent("Tad Fitzpatrick", "Pat Fitzpatrick").
parent("Trent Mcnamee", "Bo Mcnamee").
parent("Trent Mcnamee", "Karrie Mcnamee").

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

gender("Adam Mcglynn", "male").
gender("Almeta Lanza", "female").
gender("Antonia Lanza", "female").
gender("Benito Matheson", "male").
gender("Bobby Kingery", "male").
gender("Ellen Munguia", "female").
gender("Harold Grayson", "male").
gender("Hiram Lanza", "male").
gender("Ivette Kingery", "female").
gender("Jimmie Kingery", "male").
gender("Johnetta Matheson", "female").
gender("Kerry Grayson", "female").
gender("Lane Mcglynn", "male").
gender("Lindsey Grayson", "female").
gender("Magdalene Matheson", "female").
gender("Manuel Matheson", "male").
gender("Mariann Grayson", "female").
gender("Maurice Grayson", "male").
gender("Michell Kingery", "female").
gender("Rolando Matheson", "male").
gender("Samual Grayson", "male").
gender("Sara Matheson", "female").
gender("Shaina Mcglynn", "female").
gender("Tamala Munguia", "female").
gender("Timmy Munguia", "male").
gender("Alberto Vogel", "male").
gender("Barry Mcnamee", "male").
gender("Bo Mcnamee", "male").
gender("Carmon Bledsoe", "female").
gender("Charley Mcnamee", "male").
gender("Colleen Mcnamee", "female").
gender("Deidre Fitzpatrick", "female").
gender("Eddy Bledsoe", "male").
gender("Emmett Bledsoe", "male").
gender("Everett Mcnamee", "male").
gender("Jacquelyn Mcnamee", "female").
gender("Joe Bledsoe", "male").
gender("Karrie Mcnamee", "female").
gender("Kieth Mcnamee", "male").
gender("Krystle Vogel", "female").
gender("Lanny Mcnamee", "male").
gender("Lona Bledsoe", "female").
gender("Myrl Mcnamee", "female").
gender("Pat Fitzpatrick", "male").
gender("Pauline Mcnamee", "female").
gender("Philip Bledsoe", "male").
gender("Rasheeda Bledsoe", "female").
gender("Reyes Mcnamee", "male").
gender("Shaunte Mcnamee", "female").
gender("Tad Fitzpatrick", "male").
gender("Trent Mcnamee", "male").

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

friend_("Adam Mcglynn", "Lane Mcglynn").
friend_("Adam Mcglynn", "Michell Kingery").
friend_("Adam Mcglynn", "Karrie Mcnamee").
friend_("Almeta Lanza", "Bobby Kingery").
friend_("Almeta Lanza", "Charley Mcnamee").
friend_("Almeta Lanza", "Eddy Bledsoe").
friend_("Antonia Lanza", "Ellen Munguia").
friend_("Antonia Lanza", "Manuel Matheson").
friend_("Antonia Lanza", "Everett Mcnamee").
friend_("Benito Matheson", "Ellen Munguia").
friend_("Benito Matheson", "Kerry Grayson").
friend_("Bobby Kingery", "Lane Mcglynn").
friend_("Bobby Kingery", "Shaina Mcglynn").
friend_("Bobby Kingery", "Trent Mcnamee").
friend_("Ellen Munguia", "Lindsey Grayson").
friend_("Ellen Munguia", "Tamala Munguia").
friend_("Ellen Munguia", "Alberto Vogel").
friend_("Harold Grayson", "Alberto Vogel").
friend_("Harold Grayson", "Jacquelyn Mcnamee").
friend_("Harold Grayson", "Trent Mcnamee").
friend_("Hiram Lanza", "Michell Kingery").
friend_("Hiram Lanza", "Timmy Munguia").
friend_("Hiram Lanza", "Barry Mcnamee").
friend_("Hiram Lanza", "Pat Fitzpatrick").
friend_("Hiram Lanza", "Philip Bledsoe").
friend_("Ivette Kingery", "Emmett Bledsoe").
friend_("Jimmie Kingery", "Manuel Matheson").
friend_("Johnetta Matheson", "Kerry Grayson").
friend_("Johnetta Matheson", "Everett Mcnamee").
friend_("Kerry Grayson", "Karrie Mcnamee").
friend_("Lane Mcglynn", "Manuel Matheson").
friend_("Lane Mcglynn", "Krystle Vogel").
friend_("Lindsey Grayson", "Michell Kingery").
friend_("Magdalene Matheson", "Manuel Matheson").
friend_("Magdalene Matheson", "Deidre Fitzpatrick").
friend_("Magdalene Matheson", "Rasheeda Bledsoe").
friend_("Magdalene Matheson", "Shaunte Mcnamee").
friend_("Magdalene Matheson", "Trent Mcnamee").
friend_("Manuel Matheson", "Jacquelyn Mcnamee").
friend_("Manuel Matheson", "Joe Bledsoe").
friend_("Manuel Matheson", "Philip Bledsoe").
friend_("Mariann Grayson", "Deidre Fitzpatrick").
friend_("Michell Kingery", "Everett Mcnamee").
friend_("Michell Kingery", "Philip Bledsoe").
friend_("Rolando Matheson", "Trent Mcnamee").
friend_("Sara Matheson", "Myrl Mcnamee").
friend_("Shaina Mcglynn", "Reyes Mcnamee").
friend_("Shaina Mcglynn", "Tad Fitzpatrick").
friend_("Tamala Munguia", "Kieth Mcnamee").
friend_("Timmy Munguia", "Reyes Mcnamee").
friend_("Barry Mcnamee", "Philip Bledsoe").
friend_("Barry Mcnamee", "Reyes Mcnamee").
friend_("Barry Mcnamee", "Trent Mcnamee").
friend_("Bo Mcnamee", "Everett Mcnamee").
friend_("Carmon Bledsoe", "Philip Bledsoe").
friend_("Carmon Bledsoe", "Shaunte Mcnamee").
friend_("Deidre Fitzpatrick", "Shaunte Mcnamee").
friend_("Deidre Fitzpatrick", "Tad Fitzpatrick").
friend_("Eddy Bledsoe", "Jacquelyn Mcnamee").
friend_("Eddy Bledsoe", "Lona Bledsoe").
friend_("Eddy Bledsoe", "Tad Fitzpatrick").
friend_("Jacquelyn Mcnamee", "Trent Mcnamee").
friend_("Joe Bledsoe", "Myrl Mcnamee").
friend_("Karrie Mcnamee", "Kieth Mcnamee").
friend_("Karrie Mcnamee", "Reyes Mcnamee").
friend_("Krystle Vogel", "Trent Mcnamee").
friend_("Pat Fitzpatrick", "Tad Fitzpatrick").
friend_("Shaunte Mcnamee", "Trent Mcnamee").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("production designer").
attribute("insect collecting").
attribute("commissioning editor").
attribute("phillumeny").
attribute("scientist").
attribute("fishing").
attribute("optician").
attribute("fishkeeping").
attribute("sports development officer").
attribute("sea glass collecting").
attribute("senior tax professional").
attribute("element collecting").
attribute("graphic designer").
attribute("learning").
attribute("technical sales engineer").
attribute("linguistics").
attribute("advertising account executive").
attribute("butterfly watching").
attribute("arts development officer").
attribute("longboarding").
attribute("mudlogger").
attribute("research").
attribute("dietitian").
attribute("sports science").
attribute("neurosurgeon").
attribute("baking").
attribute("chemical engineer").
attribute("lacrosse").
attribute("fisheries officer").
attribute("lacrosse").
attribute("counsellor").
attribute("antiquities").
attribute("geoscientist").
attribute("people-watching").
attribute("lexicographer").
attribute("taekwondo").
attribute("land surveyor").
attribute("judo").
attribute("pilot").
attribute("volleyball").
attribute("statistician").
attribute("beekeeping").
attribute("education officer").
attribute("sea glass collecting").
attribute("general practice doctor").
attribute("teaching").
attribute("banker").
attribute("gymnastics").
attribute("podiatrist").
attribute("table tennis").
attribute("financial manager").
attribute("field hockey").
attribute("field seismologist").
attribute("animation").
attribute("statistician").
attribute("flower collecting and pressing").
attribute("programmer").
attribute("amateur astronomy").
attribute("aid worker").
attribute("jurisprudential").
attribute("furniture designer").
attribute("flower collecting and pressing").
attribute("medical illustrator").
attribute("scouting").
attribute("education administrator").
attribute("water polo").
attribute("graphic designer").
attribute("myrmecology").
attribute("physiological scientist").
attribute("benchmarking").
attribute("marine scientist").
attribute("satellite watching").
attribute("immunologist").
attribute("color guard").
attribute("water quality scientist").
attribute("birdwatching").
attribute("systems developer").
attribute("boxing").
attribute("recruitment consultant").
attribute("button collecting").
attribute("health visitor").
attribute("films").
attribute("teacher").
attribute("antiquities").
attribute("water quality scientist").
attribute("shooting").
attribute("records manager").
attribute("notaphily").
attribute("insurance account manager").
attribute("dominoes").
attribute("travel agency manager").
attribute("geography").
attribute("building surveyor").
attribute("footbag").
attribute("film editor").
attribute("leaves").
attribute("bookseller").
attribute("gongoozling").
attribute("charity fundraiser").
attribute("reading").
attribute("architect").
attribute("volleyball").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adam Mcglynn", person).
type("Almeta Lanza", person).
type("Antonia Lanza", person).
type("Benito Matheson", person).
type("Bobby Kingery", person).
type("Ellen Munguia", person).
type("Harold Grayson", person).
type("Hiram Lanza", person).
type("Ivette Kingery", person).
type("Jimmie Kingery", person).
type("Johnetta Matheson", person).
type("Kerry Grayson", person).
type("Lane Mcglynn", person).
type("Lindsey Grayson", person).
type("Magdalene Matheson", person).
type("Manuel Matheson", person).
type("Mariann Grayson", person).
type("Maurice Grayson", person).
type("Michell Kingery", person).
type("Rolando Matheson", person).
type("Samual Grayson", person).
type("Sara Matheson", person).
type("Shaina Mcglynn", person).
type("Tamala Munguia", person).
type("Timmy Munguia", person).
type("Alberto Vogel", person).
type("Barry Mcnamee", person).
type("Bo Mcnamee", person).
type("Carmon Bledsoe", person).
type("Charley Mcnamee", person).
type("Colleen Mcnamee", person).
type("Deidre Fitzpatrick", person).
type("Eddy Bledsoe", person).
type("Emmett Bledsoe", person).
type("Everett Mcnamee", person).
type("Jacquelyn Mcnamee", person).
type("Joe Bledsoe", person).
type("Karrie Mcnamee", person).
type("Kieth Mcnamee", person).
type("Krystle Vogel", person).
type("Lanny Mcnamee", person).
type("Lona Bledsoe", person).
type("Myrl Mcnamee", person).
type("Pat Fitzpatrick", person).
type("Pauline Mcnamee", person).
type("Philip Bledsoe", person).
type("Rasheeda Bledsoe", person).
type("Reyes Mcnamee", person).
type("Shaunte Mcnamee", person).
type("Tad Fitzpatrick", person).
type("Trent Mcnamee", person).

:- dynamic dob/2.

dob("Adam Mcglynn", "0254-02-09").
dob("Almeta Lanza", "0278-05-01").
dob("Antonia Lanza", "0305-06-15").
dob("Benito Matheson", "0226-05-21").
dob("Bobby Kingery", "0335-07-15").
dob("Ellen Munguia", "0226-02-03").
dob("Harold Grayson", "0286-07-01").
dob("Hiram Lanza", "0278-03-08").
dob("Ivette Kingery", "0308-05-15").
dob("Jimmie Kingery", "0306-02-21").
dob("Johnetta Matheson", "0221-03-19").
dob("Kerry Grayson", "0282-04-04").
dob("Lane Mcglynn", "0280-02-22").
dob("Lindsey Grayson", "0257-05-18").
dob("Magdalene Matheson", "0283-03-15").
dob("Manuel Matheson", "0253-01-08").
dob("Mariann Grayson", "0312-09-21").
dob("Maurice Grayson", "0259-12-15").
dob("Michell Kingery", "0337-10-03").
dob("Rolando Matheson", "0257-01-29").
dob("Samual Grayson", "0310-11-06").
dob("Sara Matheson", "0252-05-24").
dob("Shaina Mcglynn", "0255-01-17").
dob("Tamala Munguia", "0195-06-03").
dob("Timmy Munguia", "0196-03-05").
dob("Alberto Vogel", "0230-01-26").
dob("Barry Mcnamee", "0315-10-12").
dob("Bo Mcnamee", "0286-06-29").
dob("Carmon Bledsoe", "0260-03-26").
dob("Charley Mcnamee", "0312-12-13").
dob("Colleen Mcnamee", "0313-01-28").
dob("Deidre Fitzpatrick", "0286-01-18").
dob("Eddy Bledsoe", "0260-08-15").
dob("Emmett Bledsoe", "0290-02-19").
dob("Everett Mcnamee", "0258-06-02").
dob("Jacquelyn Mcnamee", "0256-09-25").
dob("Joe Bledsoe", "0208-07-17").
dob("Karrie Mcnamee", "0281-02-21").
dob("Kieth Mcnamee", "0334-02-12").
dob("Krystle Vogel", "0232-03-13").
dob("Lanny Mcnamee", "0310-06-14").
dob("Lona Bledsoe", "0236-08-18").
dob("Myrl Mcnamee", "0310-03-07").
dob("Pat Fitzpatrick", "0286-11-01").
dob("Pauline Mcnamee", "0306-07-23").
dob("Philip Bledsoe", "0234-04-13").
dob("Rasheeda Bledsoe", "0207-09-14").
dob("Reyes Mcnamee", "0337-05-30").
dob("Shaunte Mcnamee", "0336-02-27").
dob("Tad Fitzpatrick", "0317-03-08").
dob("Trent Mcnamee", "0313-11-02").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adam Mcglynn", "production designer").
job("Almeta Lanza", "commissioning editor").
job("Antonia Lanza", "scientist").
job("Benito Matheson", "optician").
job("Bobby Kingery", "sports development officer").
job("Ellen Munguia", "senior tax professional").
job("Harold Grayson", "graphic designer").
job("Hiram Lanza", "technical sales engineer").
job("Ivette Kingery", "advertising account executive").
job("Jimmie Kingery", "arts development officer").
job("Johnetta Matheson", "mudlogger").
job("Kerry Grayson", "dietitian").
job("Lane Mcglynn", "neurosurgeon").
job("Lindsey Grayson", "chemical engineer").
job("Magdalene Matheson", "fisheries officer").
job("Manuel Matheson", "counsellor").
job("Mariann Grayson", "geoscientist").
job("Maurice Grayson", "lexicographer").
job("Michell Kingery", "land surveyor").
job("Rolando Matheson", "pilot").
job("Samual Grayson", "statistician").
job("Sara Matheson", "education officer").
job("Shaina Mcglynn", "general practice doctor").
job("Tamala Munguia", "banker").
job("Timmy Munguia", "podiatrist").
job("Alberto Vogel", "financial manager").
job("Barry Mcnamee", "field seismologist").
job("Bo Mcnamee", "statistician").
job("Carmon Bledsoe", "programmer").
job("Charley Mcnamee", "aid worker").
job("Colleen Mcnamee", "furniture designer").
job("Deidre Fitzpatrick", "medical illustrator").
job("Eddy Bledsoe", "education administrator").
job("Emmett Bledsoe", "graphic designer").
job("Everett Mcnamee", "physiological scientist").
job("Jacquelyn Mcnamee", "marine scientist").
job("Joe Bledsoe", "immunologist").
job("Karrie Mcnamee", "water quality scientist").
job("Kieth Mcnamee", "systems developer").
job("Krystle Vogel", "recruitment consultant").
job("Lanny Mcnamee", "health visitor").
job("Lona Bledsoe", "teacher").
job("Myrl Mcnamee", "water quality scientist").
job("Pat Fitzpatrick", "records manager").
job("Pauline Mcnamee", "insurance account manager").
job("Philip Bledsoe", "travel agency manager").
job("Rasheeda Bledsoe", "building surveyor").
job("Reyes Mcnamee", "film editor").
job("Shaunte Mcnamee", "bookseller").
job("Tad Fitzpatrick", "charity fundraiser").
job("Trent Mcnamee", "architect").

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

hobby("Adam Mcglynn", "insect collecting").
hobby("Almeta Lanza", "phillumeny").
hobby("Antonia Lanza", "fishing").
hobby("Benito Matheson", "fishkeeping").
hobby("Bobby Kingery", "sea glass collecting").
hobby("Ellen Munguia", "element collecting").
hobby("Harold Grayson", "learning").
hobby("Hiram Lanza", "linguistics").
hobby("Ivette Kingery", "butterfly watching").
hobby("Jimmie Kingery", "longboarding").
hobby("Johnetta Matheson", "research").
hobby("Kerry Grayson", "sports science").
hobby("Lane Mcglynn", "baking").
hobby("Lindsey Grayson", "lacrosse").
hobby("Magdalene Matheson", "lacrosse").
hobby("Manuel Matheson", "antiquities").
hobby("Mariann Grayson", "people-watching").
hobby("Maurice Grayson", "taekwondo").
hobby("Michell Kingery", "judo").
hobby("Rolando Matheson", "volleyball").
hobby("Samual Grayson", "beekeeping").
hobby("Sara Matheson", "sea glass collecting").
hobby("Shaina Mcglynn", "teaching").
hobby("Tamala Munguia", "gymnastics").
hobby("Timmy Munguia", "table tennis").
hobby("Alberto Vogel", "field hockey").
hobby("Barry Mcnamee", "animation").
hobby("Bo Mcnamee", "flower collecting and pressing").
hobby("Carmon Bledsoe", "amateur astronomy").
hobby("Charley Mcnamee", "jurisprudential").
hobby("Colleen Mcnamee", "flower collecting and pressing").
hobby("Deidre Fitzpatrick", "scouting").
hobby("Eddy Bledsoe", "water polo").
hobby("Emmett Bledsoe", "myrmecology").
hobby("Everett Mcnamee", "benchmarking").
hobby("Jacquelyn Mcnamee", "satellite watching").
hobby("Joe Bledsoe", "color guard").
hobby("Karrie Mcnamee", "birdwatching").
hobby("Kieth Mcnamee", "boxing").
hobby("Krystle Vogel", "button collecting").
hobby("Lanny Mcnamee", "films").
hobby("Lona Bledsoe", "antiquities").
hobby("Myrl Mcnamee", "shooting").
hobby("Pat Fitzpatrick", "notaphily").
hobby("Pauline Mcnamee", "dominoes").
hobby("Philip Bledsoe", "geography").
hobby("Rasheeda Bledsoe", "footbag").
hobby("Reyes Mcnamee", "leaves").
hobby("Shaunte Mcnamee", "gongoozling").
hobby("Tad Fitzpatrick", "reading").
hobby("Trent Mcnamee", "volleyball").

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
