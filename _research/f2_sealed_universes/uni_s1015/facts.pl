
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

parent("Adrianna Roth", "Elissa Tan").
parent("Adrianna Roth", "Rupert Tan").
parent("Carmon Roth", "Melodie Roth").
parent("Carmon Roth", "Samual Roth").
parent("Dave Roth", "Leeanne Roth").
parent("Dave Roth", "Zachery Roth").
parent("Earle Roth", "Adrianna Roth").
parent("Earle Roth", "Hyman Roth").
parent("Gertrude Andresen", "Matthew Ayotte").
parent("Gertrude Andresen", "Yoko Ayotte").
parent("Herman Roth", "Melodie Roth").
parent("Herman Roth", "Samual Roth").
parent("Hyman Roth", "Pasquale Roth").
parent("Hyman Roth", "Reyna Roth").
parent("Lavonna Roth", "Adrianna Roth").
parent("Lavonna Roth", "Hyman Roth").
parent("Melodie Roth", "Claudie Andresen").
parent("Melodie Roth", "Winford Andresen").
parent("Nevin Roth", "Leeanne Roth").
parent("Nevin Roth", "Zachery Roth").
parent("Nicky Roth", "Adrianna Roth").
parent("Nicky Roth", "Hyman Roth").
parent("Orlando Roth", "Melodie Roth").
parent("Orlando Roth", "Samual Roth").
parent("Samual Roth", "Earle Roth").
parent("Samual Roth", "Karen Roth").
parent("Winford Andresen", "Gertrude Andresen").
parent("Winford Andresen", "Marko Andresen").
parent("Zachery Roth", "Melodie Roth").
parent("Zachery Roth", "Samual Roth").
parent("Adam Schiller", "Booker Schiller").
parent("Adam Schiller", "Maurine Schiller").
parent("Annette Lark", "Florian Ridgeway").
parent("Annette Lark", "Lucretia Ridgeway").
parent("Antwan Schiller", "Booker Schiller").
parent("Antwan Schiller", "Maurine Schiller").
parent("Carl Hodges", "Andres Hodges").
parent("Carl Hodges", "Niki Hodges").
parent("Catalina Keane", "Blaine Keane").
parent("Catalina Keane", "Dorathy Keane").
parent("Cody Cho", "Dortha Cho").
parent("Cody Cho", "Mario Cho").
parent("Dorathy Keane", "Erik Hodges").
parent("Dorathy Keane", "Rosie Hodges").
parent("Dortha Cho", "Annette Lark").
parent("Dortha Cho", "Woodrow Lark").
parent("Erik Hodges", "Andres Hodges").
parent("Erik Hodges", "Niki Hodges").
parent("Katelyn Hodges", "Erik Hodges").
parent("Katelyn Hodges", "Rosie Hodges").
parent("Katerine Hodges", "Erik Hodges").
parent("Katerine Hodges", "Rosie Hodges").
parent("Lakeshia Schiller", "Antwan Schiller").
parent("Lakeshia Schiller", "Leonora Schiller").
parent("Leonora Schiller", "Mitchell Cho").
parent("Leonora Schiller", "Serena Cho").
parent("Mario Cho", "Mitchell Cho").
parent("Mario Cho", "Serena Cho").
parent("Richard Cho", "Dortha Cho").
parent("Richard Cho", "Mario Cho").
parent("Rosie Hodges", "Dortha Cho").
parent("Rosie Hodges", "Mario Cho").

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

gender("Adrianna Roth", "female").
gender("Carmon Roth", "female").
gender("Claudie Andresen", "female").
gender("Dave Roth", "male").
gender("Earle Roth", "male").
gender("Elissa Tan", "female").
gender("Gertrude Andresen", "female").
gender("Herman Roth", "male").
gender("Hyman Roth", "male").
gender("Karen Roth", "female").
gender("Lavonna Roth", "female").
gender("Leeanne Roth", "female").
gender("Marko Andresen", "male").
gender("Matthew Ayotte", "male").
gender("Melodie Roth", "female").
gender("Nevin Roth", "male").
gender("Nicky Roth", "male").
gender("Orlando Roth", "male").
gender("Pasquale Roth", "male").
gender("Reyna Roth", "female").
gender("Rupert Tan", "male").
gender("Samual Roth", "male").
gender("Winford Andresen", "male").
gender("Yoko Ayotte", "female").
gender("Zachery Roth", "male").
gender("Adam Schiller", "male").
gender("Andres Hodges", "male").
gender("Annette Lark", "female").
gender("Antwan Schiller", "male").
gender("Blaine Keane", "male").
gender("Booker Schiller", "male").
gender("Carl Hodges", "male").
gender("Catalina Keane", "female").
gender("Cody Cho", "male").
gender("Dorathy Keane", "female").
gender("Dortha Cho", "female").
gender("Erik Hodges", "male").
gender("Florian Ridgeway", "male").
gender("Katelyn Hodges", "female").
gender("Katerine Hodges", "female").
gender("Lakeshia Schiller", "female").
gender("Leonora Schiller", "female").
gender("Lucretia Ridgeway", "female").
gender("Mario Cho", "male").
gender("Maurine Schiller", "female").
gender("Mitchell Cho", "male").
gender("Niki Hodges", "female").
gender("Richard Cho", "male").
gender("Rosie Hodges", "female").
gender("Serena Cho", "female").
gender("Woodrow Lark", "male").

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

friend_("Adrianna Roth", "Claudie Andresen").
friend_("Adrianna Roth", "Adam Schiller").
friend_("Adrianna Roth", "Antwan Schiller").
friend_("Adrianna Roth", "Lakeshia Schiller").
friend_("Carmon Roth", "Earle Roth").
friend_("Carmon Roth", "Rupert Tan").
friend_("Carmon Roth", "Winford Andresen").
friend_("Carmon Roth", "Booker Schiller").
friend_("Carmon Roth", "Cody Cho").
friend_("Carmon Roth", "Dorathy Keane").
friend_("Carmon Roth", "Maurine Schiller").
friend_("Carmon Roth", "Woodrow Lark").
friend_("Claudie Andresen", "Rupert Tan").
friend_("Claudie Andresen", "Yoko Ayotte").
friend_("Claudie Andresen", "Katelyn Hodges").
friend_("Claudie Andresen", "Mario Cho").
friend_("Claudie Andresen", "Rosie Hodges").
friend_("Dave Roth", "Nevin Roth").
friend_("Dave Roth", "Reyna Roth").
friend_("Dave Roth", "Winford Andresen").
friend_("Dave Roth", "Katerine Hodges").
friend_("Elissa Tan", "Katelyn Hodges").
friend_("Gertrude Andresen", "Matthew Ayotte").
friend_("Gertrude Andresen", "Rosie Hodges").
friend_("Herman Roth", "Lavonna Roth").
friend_("Herman Roth", "Nicky Roth").
friend_("Herman Roth", "Niki Hodges").
friend_("Herman Roth", "Rosie Hodges").
friend_("Hyman Roth", "Leeanne Roth").
friend_("Hyman Roth", "Niki Hodges").
friend_("Karen Roth", "Orlando Roth").
friend_("Karen Roth", "Florian Ridgeway").
friend_("Lavonna Roth", "Annette Lark").
friend_("Lavonna Roth", "Antwan Schiller").
friend_("Lavonna Roth", "Lakeshia Schiller").
friend_("Leeanne Roth", "Yoko Ayotte").
friend_("Leeanne Roth", "Maurine Schiller").
friend_("Marko Andresen", "Nevin Roth").
friend_("Marko Andresen", "Winford Andresen").
friend_("Matthew Ayotte", "Zachery Roth").
friend_("Matthew Ayotte", "Woodrow Lark").
friend_("Melodie Roth", "Catalina Keane").
friend_("Melodie Roth", "Cody Cho").
friend_("Nevin Roth", "Niki Hodges").
friend_("Nicky Roth", "Orlando Roth").
friend_("Nicky Roth", "Adam Schiller").
friend_("Nicky Roth", "Booker Schiller").
friend_("Nicky Roth", "Catalina Keane").
friend_("Nicky Roth", "Katerine Hodges").
friend_("Orlando Roth", "Katerine Hodges").
friend_("Pasquale Roth", "Yoko Ayotte").
friend_("Pasquale Roth", "Zachery Roth").
friend_("Pasquale Roth", "Serena Cho").
friend_("Reyna Roth", "Dortha Cho").
friend_("Reyna Roth", "Woodrow Lark").
friend_("Rupert Tan", "Catalina Keane").
friend_("Rupert Tan", "Mario Cho").
friend_("Winford Andresen", "Woodrow Lark").
friend_("Yoko Ayotte", "Zachery Roth").
friend_("Yoko Ayotte", "Booker Schiller").
friend_("Yoko Ayotte", "Cody Cho").
friend_("Yoko Ayotte", "Florian Ridgeway").
friend_("Yoko Ayotte", "Mitchell Cho").
friend_("Zachery Roth", "Cody Cho").
friend_("Adam Schiller", "Annette Lark").
friend_("Adam Schiller", "Antwan Schiller").
friend_("Annette Lark", "Booker Schiller").
friend_("Annette Lark", "Maurine Schiller").
friend_("Annette Lark", "Mitchell Cho").
friend_("Antwan Schiller", "Dorathy Keane").
friend_("Antwan Schiller", "Erik Hodges").
friend_("Blaine Keane", "Cody Cho").
friend_("Booker Schiller", "Erik Hodges").
friend_("Carl Hodges", "Maurine Schiller").
friend_("Cody Cho", "Niki Hodges").
friend_("Cody Cho", "Serena Cho").
friend_("Dorathy Keane", "Erik Hodges").
friend_("Dorathy Keane", "Lucretia Ridgeway").
friend_("Florian Ridgeway", "Lakeshia Schiller").
friend_("Florian Ridgeway", "Niki Hodges").
friend_("Florian Ridgeway", "Woodrow Lark").
friend_("Lakeshia Schiller", "Serena Cho").
friend_("Leonora Schiller", "Lucretia Ridgeway").
friend_("Mario Cho", "Woodrow Lark").
friend_("Maurine Schiller", "Rosie Hodges").
friend_("Richard Cho", "Rosie Hodges").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("best boy").
attribute("insect collecting").
attribute("acupuncturist").
attribute("laser tag").
attribute("dance movement psychotherapist").
attribute("mahjong").
attribute("publishing rights manager").
attribute("audiophile").
attribute("market researcher").
attribute("aircraft spotting").
attribute("arboriculturist").
attribute("cornhole").
attribute("mining engineer").
attribute("element collecting").
attribute("speech and language therapist").
attribute("science and technology studies").
attribute("educational psychologist").
attribute("gardening").
attribute("tax inspector").
attribute("bus spotting").
attribute("electrical engineer").
attribute("fossil hunting").
attribute("advertising art director").
attribute("ant farming").
attribute("garment technologist").
attribute("urban exploration").
attribute("armed forces training and education officer").
attribute("reading").
attribute("seismic interpreter").
attribute("science and technology studies").
attribute("recycling officer").
attribute("model racing").
attribute("exercise physiologist").
attribute("philately").
attribute("race relations officer").
attribute("cornhole").
attribute("naval architect").
attribute("research").
attribute("art gallery manager").
attribute("mini golf").
attribute("immigration officer").
attribute("magic").
attribute("clinical cytogeneticist").
attribute("flower collecting and pressing").
attribute("automotive engineer").
attribute("religious studies").
attribute("astronomer").
attribute("pickleball").
attribute("event organiser").
attribute("meteorology").
attribute("event organiser").
attribute("finance").
attribute("television camera operator").
attribute("mahjong").
attribute("futures trader").
attribute("fruit picking").
attribute("seismic interpreter").
attribute("gongoozling").
attribute("call centre manager").
attribute("volleyball").
attribute("corporate treasurer").
attribute("research").
attribute("sports development officer").
attribute("wrestling").
attribute("pensions consultant").
attribute("wikipedia editing").
attribute("horticulturist").
attribute("birdwatching").
attribute("quantity surveyor").
attribute("checkers (draughts)").
attribute("warehouse manager").
attribute("skiing").
attribute("medical sales representative").
attribute("story writing").
attribute("health physicist").
attribute("reading").
attribute("archivist").
attribute("record collecting").
attribute("psychiatrist").
attribute("association football").
attribute("building control surveyor").
attribute("mineral collecting").
attribute("town planner").
attribute("equestrianism").
attribute("sub").
attribute("benchmarking").
attribute("exhibition designer").
attribute("cartophily").
attribute("archaeologist").
attribute("butterfly watching").
attribute("fine artist").
attribute("transit map collecting").
attribute("quantity surveyor").
attribute("microbiology").
attribute("meteorologist").
attribute("judo").
attribute("barista").
attribute("thru-hiking").
attribute("paediatric nurse").
attribute("longboarding").
attribute("archaeologist").
attribute("reading").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adrianna Roth", person).
type("Carmon Roth", person).
type("Claudie Andresen", person).
type("Dave Roth", person).
type("Earle Roth", person).
type("Elissa Tan", person).
type("Gertrude Andresen", person).
type("Herman Roth", person).
type("Hyman Roth", person).
type("Karen Roth", person).
type("Lavonna Roth", person).
type("Leeanne Roth", person).
type("Marko Andresen", person).
type("Matthew Ayotte", person).
type("Melodie Roth", person).
type("Nevin Roth", person).
type("Nicky Roth", person).
type("Orlando Roth", person).
type("Pasquale Roth", person).
type("Reyna Roth", person).
type("Rupert Tan", person).
type("Samual Roth", person).
type("Winford Andresen", person).
type("Yoko Ayotte", person).
type("Zachery Roth", person).
type("Adam Schiller", person).
type("Andres Hodges", person).
type("Annette Lark", person).
type("Antwan Schiller", person).
type("Blaine Keane", person).
type("Booker Schiller", person).
type("Carl Hodges", person).
type("Catalina Keane", person).
type("Cody Cho", person).
type("Dorathy Keane", person).
type("Dortha Cho", person).
type("Erik Hodges", person).
type("Florian Ridgeway", person).
type("Katelyn Hodges", person).
type("Katerine Hodges", person).
type("Lakeshia Schiller", person).
type("Leonora Schiller", person).
type("Lucretia Ridgeway", person).
type("Mario Cho", person).
type("Maurine Schiller", person).
type("Mitchell Cho", person).
type("Niki Hodges", person).
type("Richard Cho", person).
type("Rosie Hodges", person).
type("Serena Cho", person).
type("Woodrow Lark", person).

:- dynamic dob/2.

dob("Adrianna Roth", "0179-01-13").
dob("Carmon Roth", "0264-06-21").
dob("Claudie Andresen", "0212-01-21").
dob("Dave Roth", "0286-07-07").
dob("Earle Roth", "0205-07-19").
dob("Elissa Tan", "0148-03-06").
dob("Gertrude Andresen", "0179-03-01").
dob("Herman Roth", "0269-09-16").
dob("Hyman Roth", "0179-09-17").
dob("Karen Roth", "0206-02-03").
dob("Lavonna Roth", "0201-01-13").
dob("Leeanne Roth", "0262-08-14").
dob("Marko Andresen", "0178-01-09").
dob("Matthew Ayotte", "0149-02-01").
dob("Melodie Roth", "0237-05-16").
dob("Nevin Roth", "0291-08-02").
dob("Nicky Roth", "0209-05-22").
dob("Orlando Roth", "0257-12-23").
dob("Pasquale Roth", "0149-07-17").
dob("Reyna Roth", "0151-10-02").
dob("Rupert Tan", "0151-03-05").
dob("Samual Roth", "0233-08-24").
dob("Winford Andresen", "0211-04-24").
dob("Yoko Ayotte", "0149-08-23").
dob("Zachery Roth", "0261-05-24").
dob("Adam Schiller", "0195-12-17").
dob("Andres Hodges", "0206-11-25").
dob("Annette Lark", "0176-09-09").
dob("Antwan Schiller", "0202-08-08").
dob("Blaine Keane", "0263-09-11").
dob("Booker Schiller", "0171-01-11").
dob("Carl Hodges", "0231-12-24").
dob("Catalina Keane", "0294-10-13").
dob("Cody Cho", "0231-07-02").
dob("Dorathy Keane", "0266-10-22").
dob("Dortha Cho", "0207-10-28").
dob("Erik Hodges", "0235-06-11").
dob("Florian Ridgeway", "0148-08-22").
dob("Katelyn Hodges", "0262-02-06").
dob("Katerine Hodges", "0265-01-06").
dob("Lakeshia Schiller", "0228-12-23").
dob("Leonora Schiller", "0200-09-01").
dob("Lucretia Ridgeway", "0148-12-15").
dob("Mario Cho", "0208-02-23").
dob("Maurine Schiller", "0170-05-20").
dob("Mitchell Cho", "0176-12-07").
dob("Niki Hodges", "0204-11-08").
dob("Richard Cho", "0233-12-13").
dob("Rosie Hodges", "0236-12-05").
dob("Serena Cho", "0173-12-07").
dob("Woodrow Lark", "0179-10-24").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adrianna Roth", "best boy").
job("Carmon Roth", "acupuncturist").
job("Claudie Andresen", "dance movement psychotherapist").
job("Dave Roth", "publishing rights manager").
job("Earle Roth", "market researcher").
job("Elissa Tan", "arboriculturist").
job("Gertrude Andresen", "mining engineer").
job("Herman Roth", "speech and language therapist").
job("Hyman Roth", "educational psychologist").
job("Karen Roth", "tax inspector").
job("Lavonna Roth", "electrical engineer").
job("Leeanne Roth", "advertising art director").
job("Marko Andresen", "garment technologist").
job("Matthew Ayotte", "armed forces training and education officer").
job("Melodie Roth", "seismic interpreter").
job("Nevin Roth", "recycling officer").
job("Nicky Roth", "exercise physiologist").
job("Orlando Roth", "race relations officer").
job("Pasquale Roth", "naval architect").
job("Reyna Roth", "art gallery manager").
job("Rupert Tan", "immigration officer").
job("Samual Roth", "clinical cytogeneticist").
job("Winford Andresen", "automotive engineer").
job("Yoko Ayotte", "astronomer").
job("Zachery Roth", "event organiser").
job("Adam Schiller", "event organiser").
job("Andres Hodges", "television camera operator").
job("Annette Lark", "futures trader").
job("Antwan Schiller", "seismic interpreter").
job("Blaine Keane", "call centre manager").
job("Booker Schiller", "corporate treasurer").
job("Carl Hodges", "sports development officer").
job("Catalina Keane", "pensions consultant").
job("Cody Cho", "horticulturist").
job("Dorathy Keane", "quantity surveyor").
job("Dortha Cho", "warehouse manager").
job("Erik Hodges", "medical sales representative").
job("Florian Ridgeway", "health physicist").
job("Katelyn Hodges", "archivist").
job("Katerine Hodges", "psychiatrist").
job("Lakeshia Schiller", "building control surveyor").
job("Leonora Schiller", "town planner").
job("Lucretia Ridgeway", "sub").
job("Mario Cho", "exhibition designer").
job("Maurine Schiller", "archaeologist").
job("Mitchell Cho", "fine artist").
job("Niki Hodges", "quantity surveyor").
job("Richard Cho", "meteorologist").
job("Rosie Hodges", "barista").
job("Serena Cho", "paediatric nurse").
job("Woodrow Lark", "archaeologist").

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

hobby("Adrianna Roth", "insect collecting").
hobby("Carmon Roth", "laser tag").
hobby("Claudie Andresen", "mahjong").
hobby("Dave Roth", "audiophile").
hobby("Earle Roth", "aircraft spotting").
hobby("Elissa Tan", "cornhole").
hobby("Gertrude Andresen", "element collecting").
hobby("Herman Roth", "science and technology studies").
hobby("Hyman Roth", "gardening").
hobby("Karen Roth", "bus spotting").
hobby("Lavonna Roth", "fossil hunting").
hobby("Leeanne Roth", "ant farming").
hobby("Marko Andresen", "urban exploration").
hobby("Matthew Ayotte", "reading").
hobby("Melodie Roth", "science and technology studies").
hobby("Nevin Roth", "model racing").
hobby("Nicky Roth", "philately").
hobby("Orlando Roth", "cornhole").
hobby("Pasquale Roth", "research").
hobby("Reyna Roth", "mini golf").
hobby("Rupert Tan", "magic").
hobby("Samual Roth", "flower collecting and pressing").
hobby("Winford Andresen", "religious studies").
hobby("Yoko Ayotte", "pickleball").
hobby("Zachery Roth", "meteorology").
hobby("Adam Schiller", "finance").
hobby("Andres Hodges", "mahjong").
hobby("Annette Lark", "fruit picking").
hobby("Antwan Schiller", "gongoozling").
hobby("Blaine Keane", "volleyball").
hobby("Booker Schiller", "research").
hobby("Carl Hodges", "wrestling").
hobby("Catalina Keane", "wikipedia editing").
hobby("Cody Cho", "birdwatching").
hobby("Dorathy Keane", "checkers (draughts)").
hobby("Dortha Cho", "skiing").
hobby("Erik Hodges", "story writing").
hobby("Florian Ridgeway", "reading").
hobby("Katelyn Hodges", "record collecting").
hobby("Katerine Hodges", "association football").
hobby("Lakeshia Schiller", "mineral collecting").
hobby("Leonora Schiller", "equestrianism").
hobby("Lucretia Ridgeway", "benchmarking").
hobby("Mario Cho", "cartophily").
hobby("Maurine Schiller", "butterfly watching").
hobby("Mitchell Cho", "transit map collecting").
hobby("Niki Hodges", "microbiology").
hobby("Richard Cho", "judo").
hobby("Rosie Hodges", "thru-hiking").
hobby("Serena Cho", "longboarding").
hobby("Woodrow Lark", "reading").

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
