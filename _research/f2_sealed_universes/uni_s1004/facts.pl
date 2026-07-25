
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

parent("Adelina Shane", "Raina Springer").
parent("Adelina Shane", "Russell Springer").
parent("Alyssa Newby", "Floyd Newby").
parent("Alyssa Newby", "Pamela Newby").
parent("Buddy Gosselin", "Deloris Gosselin").
parent("Buddy Gosselin", "Ellis Gosselin").
parent("Deloris Gosselin", "Adelina Shane").
parent("Deloris Gosselin", "Chet Shane").
parent("Evette Springer", "Rodger Springer").
parent("Evette Springer", "Wanda Springer").
parent("Isaac Springer", "Kayla Springer").
parent("Isaac Springer", "Wes Springer").
parent("Joesph Springer", "Kayla Springer").
parent("Joesph Springer", "Wes Springer").
parent("Jorge Springer", "Raina Springer").
parent("Jorge Springer", "Russell Springer").
parent("Marybeth Bushnell", "Gail Springer").
parent("Marybeth Bushnell", "Jorge Springer").
parent("Pamela Newby", "Kayla Springer").
parent("Pamela Newby", "Wes Springer").
parent("Reita Springer", "Raina Springer").
parent("Reita Springer", "Russell Springer").
parent("Richard Bushnell", "Francisco Bushnell").
parent("Richard Bushnell", "Marybeth Bushnell").
parent("Rodger Springer", "Kayla Springer").
parent("Rodger Springer", "Wes Springer").
parent("Sandy Springer", "Raina Springer").
parent("Sandy Springer", "Russell Springer").
parent("Ted Shane", "Adelina Shane").
parent("Ted Shane", "Chet Shane").
parent("Wes Springer", "Gail Springer").
parent("Wes Springer", "Jorge Springer").
parent("Alvin Webber", "Laurette Webber").
parent("Alvin Webber", "Nevin Webber").
parent("Dillon Womble", "Isabell Womble").
parent("Dillon Womble", "Lorenz Womble").
parent("Elbert Arias", "Kiana Arias").
parent("Elbert Arias", "Noel Arias").
parent("Helena Womble", "Hilda Womble").
parent("Helena Womble", "Stuart Womble").
parent("Isabell Womble", "Dortha Ridgway").
parent("Isabell Womble", "Mac Ridgway").
parent("Jarvis Arias", "Alana Arias").
parent("Jarvis Arias", "Elbert Arias").
parent("Julianne Womble", "Hilda Womble").
parent("Julianne Womble", "Stuart Womble").
parent("Kiana Arias", "Isabell Womble").
parent("Kiana Arias", "Lorenz Womble").
parent("Laurette Webber", "Kiana Arias").
parent("Laurette Webber", "Noel Arias").
parent("Leonora Arias", "Alana Arias").
parent("Leonora Arias", "Elbert Arias").
parent("Lorenz Womble", "Hilda Womble").
parent("Lorenz Womble", "Stuart Womble").
parent("Matilda Arias", "Alana Arias").
parent("Matilda Arias", "Elbert Arias").
parent("Moses Womble", "Belia Womble").
parent("Moses Womble", "Dana Womble").
parent("Noel Arias", "Ethan Arias").
parent("Noel Arias", "Lera Arias").
parent("Preston Womble", "Isabell Womble").
parent("Preston Womble", "Lorenz Womble").
parent("Stuart Womble", "Belia Womble").
parent("Stuart Womble", "Dana Womble").

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

gender("Adelina Shane", "female").
gender("Alyssa Newby", "female").
gender("Buddy Gosselin", "male").
gender("Chet Shane", "male").
gender("Deloris Gosselin", "female").
gender("Ellis Gosselin", "male").
gender("Evette Springer", "female").
gender("Floyd Newby", "male").
gender("Francisco Bushnell", "male").
gender("Gail Springer", "female").
gender("Isaac Springer", "male").
gender("Joesph Springer", "male").
gender("Jorge Springer", "male").
gender("Kayla Springer", "female").
gender("Marybeth Bushnell", "female").
gender("Pamela Newby", "female").
gender("Raina Springer", "female").
gender("Reita Springer", "female").
gender("Richard Bushnell", "male").
gender("Rodger Springer", "male").
gender("Russell Springer", "male").
gender("Sandy Springer", "female").
gender("Ted Shane", "male").
gender("Wanda Springer", "female").
gender("Wes Springer", "male").
gender("Alana Arias", "female").
gender("Alvin Webber", "male").
gender("Belia Womble", "female").
gender("Dana Womble", "male").
gender("Dillon Womble", "male").
gender("Dortha Ridgway", "female").
gender("Elbert Arias", "male").
gender("Ethan Arias", "male").
gender("Helena Womble", "female").
gender("Hilda Womble", "female").
gender("Isabell Womble", "female").
gender("Jarvis Arias", "male").
gender("Julianne Womble", "female").
gender("Kiana Arias", "female").
gender("Laurette Webber", "female").
gender("Leonora Arias", "female").
gender("Lera Arias", "female").
gender("Lorenz Womble", "male").
gender("Mac Ridgway", "male").
gender("Matilda Arias", "female").
gender("Moses Womble", "male").
gender("Nevin Webber", "male").
gender("Noel Arias", "male").
gender("Preston Womble", "male").
gender("Stuart Womble", "male").

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

friend_("Adelina Shane", "Pamela Newby").
friend_("Adelina Shane", "Matilda Arias").
friend_("Alyssa Newby", "Raina Springer").
friend_("Alyssa Newby", "Alana Arias").
friend_("Alyssa Newby", "Dana Womble").
friend_("Alyssa Newby", "Kiana Arias").
friend_("Buddy Gosselin", "Deloris Gosselin").
friend_("Buddy Gosselin", "Jarvis Arias").
friend_("Buddy Gosselin", "Stuart Womble").
friend_("Chet Shane", "Jorge Springer").
friend_("Chet Shane", "Jarvis Arias").
friend_("Chet Shane", "Nevin Webber").
friend_("Ellis Gosselin", "Laurette Webber").
friend_("Ellis Gosselin", "Stuart Womble").
friend_("Floyd Newby", "Kayla Springer").
friend_("Floyd Newby", "Helena Womble").
friend_("Floyd Newby", "Leonora Arias").
friend_("Francisco Bushnell", "Dana Womble").
friend_("Francisco Bushnell", "Leonora Arias").
friend_("Francisco Bushnell", "Moses Womble").
friend_("Gail Springer", "Alana Arias").
friend_("Isaac Springer", "Rodger Springer").
friend_("Isaac Springer", "Laurette Webber").
friend_("Isaac Springer", "Noel Arias").
friend_("Joesph Springer", "Julianne Womble").
friend_("Joesph Springer", "Leonora Arias").
friend_("Jorge Springer", "Pamela Newby").
friend_("Jorge Springer", "Russell Springer").
friend_("Jorge Springer", "Sandy Springer").
friend_("Jorge Springer", "Ted Shane").
friend_("Jorge Springer", "Helena Womble").
friend_("Jorge Springer", "Kiana Arias").
friend_("Jorge Springer", "Lera Arias").
friend_("Kayla Springer", "Helena Womble").
friend_("Kayla Springer", "Laurette Webber").
friend_("Kayla Springer", "Stuart Womble").
friend_("Marybeth Bushnell", "Reita Springer").
friend_("Marybeth Bushnell", "Rodger Springer").
friend_("Marybeth Bushnell", "Dana Womble").
friend_("Marybeth Bushnell", "Lorenz Womble").
friend_("Marybeth Bushnell", "Mac Ridgway").
friend_("Pamela Newby", "Hilda Womble").
friend_("Reita Springer", "Wanda Springer").
friend_("Reita Springer", "Alvin Webber").
friend_("Reita Springer", "Dana Womble").
friend_("Reita Springer", "Lorenz Womble").
friend_("Rodger Springer", "Dortha Ridgway").
friend_("Russell Springer", "Alvin Webber").
friend_("Russell Springer", "Dana Womble").
friend_("Russell Springer", "Dortha Ridgway").
friend_("Sandy Springer", "Alana Arias").
friend_("Sandy Springer", "Alvin Webber").
friend_("Sandy Springer", "Noel Arias").
friend_("Wanda Springer", "Hilda Womble").
friend_("Wes Springer", "Alvin Webber").
friend_("Wes Springer", "Laurette Webber").
friend_("Wes Springer", "Stuart Womble").
friend_("Alana Arias", "Lera Arias").
friend_("Alana Arias", "Mac Ridgway").
friend_("Alana Arias", "Stuart Womble").
friend_("Alvin Webber", "Ethan Arias").
friend_("Alvin Webber", "Noel Arias").
friend_("Belia Womble", "Lorenz Womble").
friend_("Dana Womble", "Preston Womble").
friend_("Dillon Womble", "Jarvis Arias").
friend_("Dillon Womble", "Stuart Womble").
friend_("Elbert Arias", "Stuart Womble").
friend_("Helena Womble", "Kiana Arias").
friend_("Helena Womble", "Stuart Womble").
friend_("Hilda Womble", "Moses Womble").
friend_("Isabell Womble", "Lorenz Womble").
friend_("Isabell Womble", "Stuart Womble").
friend_("Laurette Webber", "Lera Arias").
friend_("Lera Arias", "Matilda Arias").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("hydrologist").
attribute("airsoft").
attribute("lobbyist").
attribute("biology").
attribute("forest manager").
attribute("cartophily").
attribute("logistics and distribution manager").
attribute("people-watching").
attribute("brewing technologist").
attribute("magic").
attribute("environmental consultant").
attribute("snowshoeing").
attribute("midwife").
attribute("ant farming").
attribute("mining engineer").
attribute("trainspotting").
attribute("art therapist").
attribute("cheerleading").
attribute("social researcher").
attribute("research").
attribute("systems developer").
attribute("microscopy").
attribute("web designer").
attribute("dog sport").
attribute("oceanographer").
attribute("audiophile").
attribute("fitness centre manager").
attribute("meditation").
attribute("health physicist").
attribute("history").
attribute("sales professional").
attribute("vr gaming").
attribute("architectural technologist").
attribute("knife throwing").
attribute("tourism officer").
attribute("jukskei").
attribute("research officer").
attribute("wikipedia editing").
attribute("media buyer").
attribute("reading").
attribute("management consultant").
attribute("rock balancing").
attribute("international aid worker").
attribute("magnet fishing").
attribute("forensic scientist").
attribute("hobby horsing").
attribute("conference centre manager").
attribute("auto audiophilia").
attribute("structural engineer").
attribute("auto detailing").
attribute("regulatory affairs officer").
attribute("gongoozling").
attribute("retail banker").
attribute("mineral collecting").
attribute("retail banker").
attribute("photography").
attribute("housing manager").
attribute("boxing").
attribute("art gallery manager").
attribute("skydiving").
attribute("passenger transport manager").
attribute("cartophily").
attribute("accountant").
attribute("stone collecting").
attribute("archivist").
attribute("story writing").
attribute("barista").
attribute("whale watching").
attribute("radiographer").
attribute("learning").
attribute("IT consultant").
attribute("leaves").
attribute("plant breeder").
attribute("auto detailing").
attribute("claims inspector").
attribute("research").
attribute("early years teacher").
attribute("rock balancing").
attribute("adult nurse").
attribute("ballet dancing").
attribute("dispensing optician").
attribute("neuroscience").
attribute("osteopath").
attribute("history").
attribute("English as a second language teacher").
attribute("tennis").
attribute("armed forces logistics officer").
attribute("whale watching").
attribute("special effects artist").
attribute("lapel pins").
attribute("nutritional therapist").
attribute("sports science").
attribute("colour technologist").
attribute("microscopy").
attribute("merchant navy officer").
attribute("physics").
attribute("actor").
attribute("butterfly watching").
attribute("photographer").
attribute("sociology").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adelina Shane", person).
type("Alyssa Newby", person).
type("Buddy Gosselin", person).
type("Chet Shane", person).
type("Deloris Gosselin", person).
type("Ellis Gosselin", person).
type("Evette Springer", person).
type("Floyd Newby", person).
type("Francisco Bushnell", person).
type("Gail Springer", person).
type("Isaac Springer", person).
type("Joesph Springer", person).
type("Jorge Springer", person).
type("Kayla Springer", person).
type("Marybeth Bushnell", person).
type("Pamela Newby", person).
type("Raina Springer", person).
type("Reita Springer", person).
type("Richard Bushnell", person).
type("Rodger Springer", person).
type("Russell Springer", person).
type("Sandy Springer", person).
type("Ted Shane", person).
type("Wanda Springer", person).
type("Wes Springer", person).
type("Alana Arias", person).
type("Alvin Webber", person).
type("Belia Womble", person).
type("Dana Womble", person).
type("Dillon Womble", person).
type("Dortha Ridgway", person).
type("Elbert Arias", person).
type("Ethan Arias", person).
type("Helena Womble", person).
type("Hilda Womble", person).
type("Isabell Womble", person).
type("Jarvis Arias", person).
type("Julianne Womble", person).
type("Kiana Arias", person).
type("Laurette Webber", person).
type("Leonora Arias", person).
type("Lera Arias", person).
type("Lorenz Womble", person).
type("Mac Ridgway", person).
type("Matilda Arias", person).
type("Moses Womble", person).
type("Nevin Webber", person).
type("Noel Arias", person).
type("Preston Womble", person).
type("Stuart Womble", person).

:- dynamic dob/2.

dob("Adelina Shane", "0257-02-24").
dob("Alyssa Newby", "0338-06-02").
dob("Buddy Gosselin", "0312-05-05").
dob("Chet Shane", "0258-09-08").
dob("Deloris Gosselin", "0283-04-22").
dob("Ellis Gosselin", "0279-09-02").
dob("Evette Springer", "0347-01-28").
dob("Floyd Newby", "0313-01-07").
dob("Francisco Bushnell", "0288-06-18").
dob("Gail Springer", "0260-01-28").
dob("Isaac Springer", "0311-09-15").
dob("Joesph Springer", "0309-09-13").
dob("Jorge Springer", "0260-10-14").
dob("Kayla Springer", "0285-12-13").
dob("Marybeth Bushnell", "0287-01-20").
dob("Pamela Newby", "0313-07-09").
dob("Raina Springer", "0232-01-23").
dob("Reita Springer", "0267-05-17").
dob("Richard Bushnell", "0317-05-23").
dob("Rodger Springer", "0315-07-16").
dob("Russell Springer", "0234-06-21").
dob("Sandy Springer", "0263-04-22").
dob("Ted Shane", "0281-08-18").
dob("Wanda Springer", "0314-03-12").
dob("Wes Springer", "0285-08-23").
dob("Alana Arias", "0300-06-12").
dob("Alvin Webber", "0333-06-12").
dob("Belia Womble", "0197-01-11").
dob("Dana Womble", "0199-11-02").
dob("Dillon Womble", "0278-04-26").
dob("Dortha Ridgway", "0215-12-22").
dob("Elbert Arias", "0301-03-19").
dob("Ethan Arias", "0245-10-18").
dob("Helena Womble", "0252-09-04").
dob("Hilda Womble", "0221-05-08").
dob("Isabell Womble", "0249-02-10").
dob("Jarvis Arias", "0327-01-18").
dob("Julianne Womble", "0251-10-23").
dob("Kiana Arias", "0274-11-25").
dob("Laurette Webber", "0304-12-19").
dob("Leonora Arias", "0329-01-26").
dob("Lera Arias", "0245-10-12").
dob("Lorenz Womble", "0249-11-17").
dob("Mac Ridgway", "0218-04-07").
dob("Matilda Arias", "0328-09-09").
dob("Moses Womble", "0226-05-03").
dob("Nevin Webber", "0301-04-08").
dob("Noel Arias", "0274-09-18").
dob("Preston Womble", "0271-10-16").
dob("Stuart Womble", "0223-07-24").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adelina Shane", "hydrologist").
job("Alyssa Newby", "lobbyist").
job("Buddy Gosselin", "forest manager").
job("Chet Shane", "logistics and distribution manager").
job("Deloris Gosselin", "brewing technologist").
job("Ellis Gosselin", "environmental consultant").
job("Evette Springer", "midwife").
job("Floyd Newby", "mining engineer").
job("Francisco Bushnell", "art therapist").
job("Gail Springer", "social researcher").
job("Isaac Springer", "systems developer").
job("Joesph Springer", "web designer").
job("Jorge Springer", "oceanographer").
job("Kayla Springer", "fitness centre manager").
job("Marybeth Bushnell", "health physicist").
job("Pamela Newby", "sales professional").
job("Raina Springer", "architectural technologist").
job("Reita Springer", "tourism officer").
job("Richard Bushnell", "research officer").
job("Rodger Springer", "media buyer").
job("Russell Springer", "management consultant").
job("Sandy Springer", "international aid worker").
job("Ted Shane", "forensic scientist").
job("Wanda Springer", "conference centre manager").
job("Wes Springer", "structural engineer").
job("Alana Arias", "regulatory affairs officer").
job("Alvin Webber", "retail banker").
job("Belia Womble", "retail banker").
job("Dana Womble", "housing manager").
job("Dillon Womble", "art gallery manager").
job("Dortha Ridgway", "passenger transport manager").
job("Elbert Arias", "accountant").
job("Ethan Arias", "archivist").
job("Helena Womble", "barista").
job("Hilda Womble", "radiographer").
job("Isabell Womble", "IT consultant").
job("Jarvis Arias", "plant breeder").
job("Julianne Womble", "claims inspector").
job("Kiana Arias", "early years teacher").
job("Laurette Webber", "adult nurse").
job("Leonora Arias", "dispensing optician").
job("Lera Arias", "osteopath").
job("Lorenz Womble", "English as a second language teacher").
job("Mac Ridgway", "armed forces logistics officer").
job("Matilda Arias", "special effects artist").
job("Moses Womble", "nutritional therapist").
job("Nevin Webber", "colour technologist").
job("Noel Arias", "merchant navy officer").
job("Preston Womble", "actor").
job("Stuart Womble", "photographer").

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

hobby("Adelina Shane", "airsoft").
hobby("Alyssa Newby", "biology").
hobby("Buddy Gosselin", "cartophily").
hobby("Chet Shane", "people-watching").
hobby("Deloris Gosselin", "magic").
hobby("Ellis Gosselin", "snowshoeing").
hobby("Evette Springer", "ant farming").
hobby("Floyd Newby", "trainspotting").
hobby("Francisco Bushnell", "cheerleading").
hobby("Gail Springer", "research").
hobby("Isaac Springer", "microscopy").
hobby("Joesph Springer", "dog sport").
hobby("Jorge Springer", "audiophile").
hobby("Kayla Springer", "meditation").
hobby("Marybeth Bushnell", "history").
hobby("Pamela Newby", "vr gaming").
hobby("Raina Springer", "knife throwing").
hobby("Reita Springer", "jukskei").
hobby("Richard Bushnell", "wikipedia editing").
hobby("Rodger Springer", "reading").
hobby("Russell Springer", "rock balancing").
hobby("Sandy Springer", "magnet fishing").
hobby("Ted Shane", "hobby horsing").
hobby("Wanda Springer", "auto audiophilia").
hobby("Wes Springer", "auto detailing").
hobby("Alana Arias", "gongoozling").
hobby("Alvin Webber", "mineral collecting").
hobby("Belia Womble", "photography").
hobby("Dana Womble", "boxing").
hobby("Dillon Womble", "skydiving").
hobby("Dortha Ridgway", "cartophily").
hobby("Elbert Arias", "stone collecting").
hobby("Ethan Arias", "story writing").
hobby("Helena Womble", "whale watching").
hobby("Hilda Womble", "learning").
hobby("Isabell Womble", "leaves").
hobby("Jarvis Arias", "auto detailing").
hobby("Julianne Womble", "research").
hobby("Kiana Arias", "rock balancing").
hobby("Laurette Webber", "ballet dancing").
hobby("Leonora Arias", "neuroscience").
hobby("Lera Arias", "history").
hobby("Lorenz Womble", "tennis").
hobby("Mac Ridgway", "whale watching").
hobby("Matilda Arias", "lapel pins").
hobby("Moses Womble", "sports science").
hobby("Nevin Webber", "microscopy").
hobby("Noel Arias", "physics").
hobby("Preston Womble", "butterfly watching").
hobby("Stuart Womble", "sociology").

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
