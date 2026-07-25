
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

parent("Adalberto Sparkman", "Jamel Sparkman").
parent("Adalberto Sparkman", "Marguerita Sparkman").
parent("Carmine Bible", "Lucio Bible").
parent("Carmine Bible", "Sha Bible").
parent("Douglass Pugliese", "Lashandra Pugliese").
parent("Douglass Pugliese", "Rolando Pugliese").
parent("Erick Sparkman", "Jamel Sparkman").
parent("Erick Sparkman", "Marguerita Sparkman").
parent("Francesca Sparkman", "Laurence Sparkman").
parent("Francesca Sparkman", "Sha Sparkman").
parent("Isabell Pugliese", "Lashandra Pugliese").
parent("Isabell Pugliese", "Rolando Pugliese").
parent("Isabella Sparkman", "Laurence Sparkman").
parent("Isabella Sparkman", "Sha Sparkman").
parent("Ismael Sparkman", "Laurence Sparkman").
parent("Ismael Sparkman", "Sha Sparkman").
parent("Jamel Sparkman", "Laurence Sparkman").
parent("Jamel Sparkman", "Sha Sparkman").
parent("Jeanette Vega", "Keisha Vega").
parent("Jeanette Vega", "Shon Vega").
parent("Keisha Vega", "Laurence Sparkman").
parent("Keisha Vega", "Sha Sparkman").
parent("Laurence Sparkman", "Markus Sparkman").
parent("Laurence Sparkman", "Rebecka Sparkman").
parent("Leonardo Lipsey", "Carmine Lipsey").
parent("Leonardo Lipsey", "Marie Lipsey").
parent("Marie Lipsey", "Jamel Sparkman").
parent("Marie Lipsey", "Marguerita Sparkman").
parent("Markus Sparkman", "Hiram Sparkman").
parent("Markus Sparkman", "Johnetta Sparkman").
parent("Sha Bible", "Keisha Vega").
parent("Sha Bible", "Shon Vega").
parent("Sha Sparkman", "Lashandra Pugliese").
parent("Sha Sparkman", "Rolando Pugliese").
parent("Bev Boughton", "Devin Mcneely").
parent("Bev Boughton", "Gina Mcneely").
parent("Buddy Ackerman", "Darwin Ackerman").
parent("Buddy Ackerman", "Yuk Ackerman").
parent("Chelsie Ackerman", "Mattie Ackerman").
parent("Chelsie Ackerman", "Timothy Ackerman").
parent("Darwin Ackerman", "Mattie Ackerman").
parent("Darwin Ackerman", "Timothy Ackerman").
parent("Dinah Boughton", "Mattie Ackerman").
parent("Dinah Boughton", "Timothy Ackerman").
parent("Guillermo Boughton", "Clifton Boughton").
parent("Guillermo Boughton", "Dinah Boughton").
parent("Jack Ackerman", "Darwin Ackerman").
parent("Jack Ackerman", "Yuk Ackerman").
parent("Latisha Templeton", "Delsie Templeton").
parent("Latisha Templeton", "Leonardo Templeton").
parent("Mattie Ackerman", "Delsie Templeton").
parent("Mattie Ackerman", "Leonardo Templeton").
parent("Mickey Twigg", "Dorathy Twigg").
parent("Mickey Twigg", "Gale Twigg").
parent("Neil Ackerman", "Darwin Ackerman").
parent("Neil Ackerman", "Yuk Ackerman").
parent("Richie Boughton", "Bev Boughton").
parent("Richie Boughton", "Guillermo Boughton").
parent("Susie Berglund", "Douglas Berglund").
parent("Susie Berglund", "Yasmin Berglund").
parent("Wanita Boughton", "Bev Boughton").
parent("Wanita Boughton", "Guillermo Boughton").
parent("Yasmin Berglund", "Dorathy Twigg").
parent("Yasmin Berglund", "Gale Twigg").
parent("Yuk Ackerman", "Dorathy Twigg").
parent("Yuk Ackerman", "Gale Twigg").

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

gender("Adalberto Sparkman", "male").
gender("Carmine Bible", "male").
gender("Carmine Lipsey", "male").
gender("Douglass Pugliese", "male").
gender("Erick Sparkman", "male").
gender("Francesca Sparkman", "female").
gender("Hiram Sparkman", "male").
gender("Isabell Pugliese", "female").
gender("Isabella Sparkman", "female").
gender("Ismael Sparkman", "male").
gender("Jamel Sparkman", "male").
gender("Jeanette Vega", "female").
gender("Johnetta Sparkman", "female").
gender("Keisha Vega", "female").
gender("Lashandra Pugliese", "female").
gender("Laurence Sparkman", "male").
gender("Leonardo Lipsey", "male").
gender("Lucio Bible", "male").
gender("Marguerita Sparkman", "female").
gender("Marie Lipsey", "female").
gender("Markus Sparkman", "male").
gender("Rebecka Sparkman", "female").
gender("Rolando Pugliese", "male").
gender("Sha Bible", "female").
gender("Sha Sparkman", "female").
gender("Shon Vega", "male").
gender("Bev Boughton", "female").
gender("Buddy Ackerman", "male").
gender("Chelsie Ackerman", "female").
gender("Clifton Boughton", "male").
gender("Darwin Ackerman", "male").
gender("Delsie Templeton", "female").
gender("Devin Mcneely", "male").
gender("Dinah Boughton", "female").
gender("Dorathy Twigg", "female").
gender("Douglas Berglund", "male").
gender("Gale Twigg", "male").
gender("Gina Mcneely", "female").
gender("Guillermo Boughton", "male").
gender("Jack Ackerman", "male").
gender("Latisha Templeton", "female").
gender("Leonardo Templeton", "male").
gender("Mattie Ackerman", "female").
gender("Mickey Twigg", "male").
gender("Neil Ackerman", "male").
gender("Richie Boughton", "male").
gender("Susie Berglund", "female").
gender("Timothy Ackerman", "male").
gender("Wanita Boughton", "female").
gender("Yasmin Berglund", "female").
gender("Yuk Ackerman", "female").

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

friend_("Adalberto Sparkman", "Sha Bible").
friend_("Adalberto Sparkman", "Richie Boughton").
friend_("Adalberto Sparkman", "Timothy Ackerman").
friend_("Adalberto Sparkman", "Wanita Boughton").
friend_("Carmine Bible", "Francesca Sparkman").
friend_("Carmine Bible", "Hiram Sparkman").
friend_("Carmine Bible", "Yuk Ackerman").
friend_("Carmine Lipsey", "Hiram Sparkman").
friend_("Carmine Lipsey", "Clifton Boughton").
friend_("Erick Sparkman", "Shon Vega").
friend_("Erick Sparkman", "Bev Boughton").
friend_("Erick Sparkman", "Yuk Ackerman").
friend_("Francesca Sparkman", "Chelsie Ackerman").
friend_("Francesca Sparkman", "Latisha Templeton").
friend_("Francesca Sparkman", "Mickey Twigg").
friend_("Hiram Sparkman", "Isabell Pugliese").
friend_("Hiram Sparkman", "Guillermo Boughton").
friend_("Isabell Pugliese", "Leonardo Lipsey").
friend_("Isabell Pugliese", "Gina Mcneely").
friend_("Isabell Pugliese", "Susie Berglund").
friend_("Isabella Sparkman", "Richie Boughton").
friend_("Isabella Sparkman", "Susie Berglund").
friend_("Ismael Sparkman", "Keisha Vega").
friend_("Ismael Sparkman", "Bev Boughton").
friend_("Ismael Sparkman", "Gale Twigg").
friend_("Ismael Sparkman", "Guillermo Boughton").
friend_("Ismael Sparkman", "Yuk Ackerman").
friend_("Jamel Sparkman", "Laurence Sparkman").
friend_("Jamel Sparkman", "Dorathy Twigg").
friend_("Jeanette Vega", "Devin Mcneely").
friend_("Johnetta Sparkman", "Leonardo Lipsey").
friend_("Johnetta Sparkman", "Markus Sparkman").
friend_("Johnetta Sparkman", "Clifton Boughton").
friend_("Johnetta Sparkman", "Dorathy Twigg").
friend_("Keisha Vega", "Lashandra Pugliese").
friend_("Keisha Vega", "Sha Sparkman").
friend_("Keisha Vega", "Clifton Boughton").
friend_("Keisha Vega", "Dinah Boughton").
friend_("Keisha Vega", "Guillermo Boughton").
friend_("Keisha Vega", "Leonardo Templeton").
friend_("Lashandra Pugliese", "Marguerita Sparkman").
friend_("Laurence Sparkman", "Delsie Templeton").
friend_("Laurence Sparkman", "Susie Berglund").
friend_("Leonardo Lipsey", "Lucio Bible").
friend_("Leonardo Lipsey", "Marguerita Sparkman").
friend_("Leonardo Lipsey", "Rebecka Sparkman").
friend_("Leonardo Lipsey", "Dorathy Twigg").
friend_("Lucio Bible", "Rolando Pugliese").
friend_("Lucio Bible", "Dinah Boughton").
friend_("Lucio Bible", "Yuk Ackerman").
friend_("Marguerita Sparkman", "Timothy Ackerman").
friend_("Marie Lipsey", "Jack Ackerman").
friend_("Markus Sparkman", "Timothy Ackerman").
friend_("Rebecka Sparkman", "Sha Sparkman").
friend_("Rebecka Sparkman", "Douglas Berglund").
friend_("Rebecka Sparkman", "Neil Ackerman").
friend_("Rebecka Sparkman", "Yasmin Berglund").
friend_("Rebecka Sparkman", "Yuk Ackerman").
friend_("Rolando Pugliese", "Chelsie Ackerman").
friend_("Rolando Pugliese", "Mickey Twigg").
friend_("Rolando Pugliese", "Wanita Boughton").
friend_("Sha Sparkman", "Latisha Templeton").
friend_("Sha Sparkman", "Timothy Ackerman").
friend_("Sha Sparkman", "Yasmin Berglund").
friend_("Shon Vega", "Buddy Ackerman").
friend_("Shon Vega", "Yuk Ackerman").
friend_("Bev Boughton", "Buddy Ackerman").
friend_("Bev Boughton", "Richie Boughton").
friend_("Buddy Ackerman", "Neil Ackerman").
friend_("Buddy Ackerman", "Wanita Boughton").
friend_("Chelsie Ackerman", "Richie Boughton").
friend_("Chelsie Ackerman", "Wanita Boughton").
friend_("Clifton Boughton", "Dorathy Twigg").
friend_("Clifton Boughton", "Neil Ackerman").
friend_("Clifton Boughton", "Susie Berglund").
friend_("Delsie Templeton", "Dorathy Twigg").
friend_("Devin Mcneely", "Dinah Boughton").
friend_("Dinah Boughton", "Dorathy Twigg").
friend_("Dinah Boughton", "Susie Berglund").
friend_("Dorathy Twigg", "Jack Ackerman").
friend_("Douglas Berglund", "Yasmin Berglund").
friend_("Guillermo Boughton", "Richie Boughton").
friend_("Guillermo Boughton", "Timothy Ackerman").
friend_("Leonardo Templeton", "Mickey Twigg").
friend_("Mattie Ackerman", "Mickey Twigg").
friend_("Mickey Twigg", "Wanita Boughton").
friend_("Neil Ackerman", "Wanita Boughton").
friend_("Neil Ackerman", "Yasmin Berglund").
friend_("Susie Berglund", "Yuk Ackerman").
friend_("Timothy Ackerman", "Yasmin Berglund").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("journalist").
attribute("leaves").
attribute("medical laboratory scientific officer").
attribute("microscopy").
attribute("print production planner").
attribute("tai chi").
attribute("contracting civil engineer").
attribute("vinyl records").
attribute("proofreader").
attribute("movie memorabilia collecting").
attribute("adult guidance worker").
attribute("benchmarking").
attribute("audiological scientist").
attribute("stuffed toy collecting").
attribute("learning mentor").
attribute("rail transport modelling").
attribute("air traffic controller").
attribute("tourism").
attribute("agricultural consultant").
attribute("physics").
attribute("programme researcher").
attribute("slot car").
attribute("higher education careers adviser").
attribute("meditation").
attribute("nature conservation officer").
attribute("insect collecting").
attribute("psychiatrist").
attribute("motor sports").
attribute("sports administrator").
attribute("knowledge/word games").
attribute("horticultural therapist").
attribute("composting").
attribute("human resources officer").
attribute("movie memorabilia collecting").
attribute("herpetologist").
attribute("shortwave listening").
attribute("estate manager").
attribute("neuroscience").
attribute("communications engineer").
attribute("karting").
attribute("ship broker").
attribute("stone collecting").
attribute("midwife").
attribute("geography").
attribute("personal assistant").
attribute("geocaching").
attribute("statistician").
attribute("insect collecting").
attribute("dispensing optician").
attribute("videography").
attribute("public affairs consultant").
attribute("magic").
attribute("occupational hygienist").
attribute("airsoft").
attribute("production engineer").
attribute("benchmarking").
attribute("ranger").
attribute("flower collecting and pressing").
attribute("amenity horticulturist").
attribute("die-cast toy").
attribute("English as a foreign language teacher").
attribute("fusilately").
attribute("environmental manager").
attribute("whale watching").
attribute("legal secretary").
attribute("microbiology").
attribute("haematologist").
attribute("auto audiophilia").
attribute("retail buyer").
attribute("reading").
attribute("broadcast engineer").
attribute("fossil hunting").
attribute("surgeon").
attribute("vintage clothing").
attribute("artist").
attribute("seashell collecting").
attribute("meteorologist").
attribute("research").
attribute("contractor").
attribute("mycology").
attribute("cabin crew").
attribute("surfing").
attribute("claims inspector").
attribute("volleyball").
attribute("herbalist").
attribute("perfume").
attribute("community development worker").
attribute("compact discs").
attribute("insurance risk surveyor").
attribute("model racing").
attribute("conservator").
attribute("research").
attribute("materials engineer").
attribute("auto audiophilia").
attribute("race relations officer").
attribute("satellite watching").
attribute("risk analyst").
attribute("publishing").
attribute("accountant").
attribute("scouting").
attribute("further education lecturer").
attribute("bus spotting").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adalberto Sparkman", person).
type("Carmine Bible", person).
type("Carmine Lipsey", person).
type("Douglass Pugliese", person).
type("Erick Sparkman", person).
type("Francesca Sparkman", person).
type("Hiram Sparkman", person).
type("Isabell Pugliese", person).
type("Isabella Sparkman", person).
type("Ismael Sparkman", person).
type("Jamel Sparkman", person).
type("Jeanette Vega", person).
type("Johnetta Sparkman", person).
type("Keisha Vega", person).
type("Lashandra Pugliese", person).
type("Laurence Sparkman", person).
type("Leonardo Lipsey", person).
type("Lucio Bible", person).
type("Marguerita Sparkman", person).
type("Marie Lipsey", person).
type("Markus Sparkman", person).
type("Rebecka Sparkman", person).
type("Rolando Pugliese", person).
type("Sha Bible", person).
type("Sha Sparkman", person).
type("Shon Vega", person).
type("Bev Boughton", person).
type("Buddy Ackerman", person).
type("Chelsie Ackerman", person).
type("Clifton Boughton", person).
type("Darwin Ackerman", person).
type("Delsie Templeton", person).
type("Devin Mcneely", person).
type("Dinah Boughton", person).
type("Dorathy Twigg", person).
type("Douglas Berglund", person).
type("Gale Twigg", person).
type("Gina Mcneely", person).
type("Guillermo Boughton", person).
type("Jack Ackerman", person).
type("Latisha Templeton", person).
type("Leonardo Templeton", person).
type("Mattie Ackerman", person).
type("Mickey Twigg", person).
type("Neil Ackerman", person).
type("Richie Boughton", person).
type("Susie Berglund", person).
type("Timothy Ackerman", person).
type("Wanita Boughton", person).
type("Yasmin Berglund", person).
type("Yuk Ackerman", person).

:- dynamic dob/2.

dob("Adalberto Sparkman", "0289-11-01").
dob("Carmine Bible", "0320-02-07").
dob("Carmine Lipsey", "0289-01-16").
dob("Douglass Pugliese", "0236-04-19").
dob("Erick Sparkman", "0288-10-15").
dob("Francesca Sparkman", "0261-11-16").
dob("Hiram Sparkman", "0177-11-08").
dob("Isabell Pugliese", "0233-07-20").
dob("Isabella Sparkman", "0264-06-20").
dob("Ismael Sparkman", "0265-08-13").
dob("Jamel Sparkman", "0263-01-08").
dob("Jeanette Vega", "0289-04-04").
dob("Johnetta Sparkman", "0177-01-26").
dob("Keisha Vega", "0263-01-08").
dob("Lashandra Pugliese", "0203-02-24").
dob("Laurence Sparkman", "0235-03-12").
dob("Leonardo Lipsey", "0321-02-21").
dob("Lucio Bible", "0290-01-24").
dob("Marguerita Sparkman", "0261-12-14").
dob("Marie Lipsey", "0291-07-02").
dob("Markus Sparkman", "0207-02-07").
dob("Rebecka Sparkman", "0206-08-07").
dob("Rolando Pugliese", "0206-04-03").
dob("Sha Bible", "0291-07-02").
dob("Sha Sparkman", "0233-09-11").
dob("Shon Vega", "0263-01-19").
dob("Bev Boughton", "0258-02-10").
dob("Buddy Ackerman", "0256-06-30").
dob("Chelsie Ackerman", "0227-10-11").
dob("Clifton Boughton", "0232-08-28").
dob("Darwin Ackerman", "0227-10-11").
dob("Delsie Templeton", "0175-09-26").
dob("Devin Mcneely", "0227-06-03").
dob("Dinah Boughton", "0231-02-28").
dob("Dorathy Twigg", "0198-11-04").
dob("Douglas Berglund", "0222-12-28").
dob("Gale Twigg", "0200-07-05").
dob("Gina Mcneely", "0230-08-10").
dob("Guillermo Boughton", "0259-07-04").
dob("Jack Ackerman", "0252-09-09").
dob("Latisha Templeton", "0208-10-06").
dob("Leonardo Templeton", "0177-07-19").
dob("Mattie Ackerman", "0203-06-20").
dob("Mickey Twigg", "0224-04-11").
dob("Neil Ackerman", "0252-07-20").
dob("Richie Boughton", "0287-06-29").
dob("Susie Berglund", "0255-01-03").
dob("Timothy Ackerman", "0205-09-09").
dob("Wanita Boughton", "0288-12-23").
dob("Yasmin Berglund", "0222-04-06").
dob("Yuk Ackerman", "0227-05-02").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adalberto Sparkman", "journalist").
job("Carmine Bible", "medical laboratory scientific officer").
job("Carmine Lipsey", "print production planner").
job("Douglass Pugliese", "contracting civil engineer").
job("Erick Sparkman", "proofreader").
job("Francesca Sparkman", "adult guidance worker").
job("Hiram Sparkman", "audiological scientist").
job("Isabell Pugliese", "learning mentor").
job("Isabella Sparkman", "air traffic controller").
job("Ismael Sparkman", "agricultural consultant").
job("Jamel Sparkman", "programme researcher").
job("Jeanette Vega", "higher education careers adviser").
job("Johnetta Sparkman", "nature conservation officer").
job("Keisha Vega", "psychiatrist").
job("Lashandra Pugliese", "sports administrator").
job("Laurence Sparkman", "horticultural therapist").
job("Leonardo Lipsey", "human resources officer").
job("Lucio Bible", "herpetologist").
job("Marguerita Sparkman", "estate manager").
job("Marie Lipsey", "communications engineer").
job("Markus Sparkman", "ship broker").
job("Rebecka Sparkman", "midwife").
job("Rolando Pugliese", "personal assistant").
job("Sha Bible", "statistician").
job("Sha Sparkman", "dispensing optician").
job("Shon Vega", "public affairs consultant").
job("Bev Boughton", "occupational hygienist").
job("Buddy Ackerman", "production engineer").
job("Chelsie Ackerman", "ranger").
job("Clifton Boughton", "amenity horticulturist").
job("Darwin Ackerman", "English as a foreign language teacher").
job("Delsie Templeton", "environmental manager").
job("Devin Mcneely", "legal secretary").
job("Dinah Boughton", "haematologist").
job("Dorathy Twigg", "retail buyer").
job("Douglas Berglund", "broadcast engineer").
job("Gale Twigg", "surgeon").
job("Gina Mcneely", "artist").
job("Guillermo Boughton", "meteorologist").
job("Jack Ackerman", "contractor").
job("Latisha Templeton", "cabin crew").
job("Leonardo Templeton", "claims inspector").
job("Mattie Ackerman", "herbalist").
job("Mickey Twigg", "community development worker").
job("Neil Ackerman", "insurance risk surveyor").
job("Richie Boughton", "conservator").
job("Susie Berglund", "materials engineer").
job("Timothy Ackerman", "race relations officer").
job("Wanita Boughton", "risk analyst").
job("Yasmin Berglund", "accountant").
job("Yuk Ackerman", "further education lecturer").

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

hobby("Adalberto Sparkman", "leaves").
hobby("Carmine Bible", "microscopy").
hobby("Carmine Lipsey", "tai chi").
hobby("Douglass Pugliese", "vinyl records").
hobby("Erick Sparkman", "movie memorabilia collecting").
hobby("Francesca Sparkman", "benchmarking").
hobby("Hiram Sparkman", "stuffed toy collecting").
hobby("Isabell Pugliese", "rail transport modelling").
hobby("Isabella Sparkman", "tourism").
hobby("Ismael Sparkman", "physics").
hobby("Jamel Sparkman", "slot car").
hobby("Jeanette Vega", "meditation").
hobby("Johnetta Sparkman", "insect collecting").
hobby("Keisha Vega", "motor sports").
hobby("Lashandra Pugliese", "knowledge/word games").
hobby("Laurence Sparkman", "composting").
hobby("Leonardo Lipsey", "movie memorabilia collecting").
hobby("Lucio Bible", "shortwave listening").
hobby("Marguerita Sparkman", "neuroscience").
hobby("Marie Lipsey", "karting").
hobby("Markus Sparkman", "stone collecting").
hobby("Rebecka Sparkman", "geography").
hobby("Rolando Pugliese", "geocaching").
hobby("Sha Bible", "insect collecting").
hobby("Sha Sparkman", "videography").
hobby("Shon Vega", "magic").
hobby("Bev Boughton", "airsoft").
hobby("Buddy Ackerman", "benchmarking").
hobby("Chelsie Ackerman", "flower collecting and pressing").
hobby("Clifton Boughton", "die-cast toy").
hobby("Darwin Ackerman", "fusilately").
hobby("Delsie Templeton", "whale watching").
hobby("Devin Mcneely", "microbiology").
hobby("Dinah Boughton", "auto audiophilia").
hobby("Dorathy Twigg", "reading").
hobby("Douglas Berglund", "fossil hunting").
hobby("Gale Twigg", "vintage clothing").
hobby("Gina Mcneely", "seashell collecting").
hobby("Guillermo Boughton", "research").
hobby("Jack Ackerman", "mycology").
hobby("Latisha Templeton", "surfing").
hobby("Leonardo Templeton", "volleyball").
hobby("Mattie Ackerman", "perfume").
hobby("Mickey Twigg", "compact discs").
hobby("Neil Ackerman", "model racing").
hobby("Richie Boughton", "research").
hobby("Susie Berglund", "auto audiophilia").
hobby("Timothy Ackerman", "satellite watching").
hobby("Wanita Boughton", "publishing").
hobby("Yasmin Berglund", "scouting").
hobby("Yuk Ackerman", "bus spotting").

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
