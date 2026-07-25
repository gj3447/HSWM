
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

parent("Angelo Hylton", "Anton Hylton").
parent("Angelo Hylton", "Deirdre Hylton").
parent("Dewitt Eddings", "Joaquin Eddings").
parent("Dewitt Eddings", "Victoria Eddings").
parent("Dominique Moyer", "Nelly Alanis").
parent("Dominique Moyer", "Pasquale Alanis").
parent("Eduardo Moyer", "Farrah Moyer").
parent("Eduardo Moyer", "Steve Moyer").
parent("Farrah Moyer", "Anton Hylton").
parent("Farrah Moyer", "Deirdre Hylton").
parent("Jacquline Moyer", "Cristopher Shiver").
parent("Jacquline Moyer", "Virgina Shiver").
parent("Janis Moyer", "Farrah Moyer").
parent("Janis Moyer", "Steve Moyer").
parent("Jeanette Moyer", "Dominique Moyer").
parent("Jeanette Moyer", "Eduardo Moyer").
parent("Jimmie Hylton", "Anton Hylton").
parent("Jimmie Hylton", "Deirdre Hylton").
parent("Kacey Green", "Jesus Green").
parent("Kacey Green", "Miki Green").
parent("Mack Moyer", "Dominique Moyer").
parent("Mack Moyer", "Eduardo Moyer").
parent("Mammie Rayford", "Dick Rayford").
parent("Mammie Rayford", "Marlana Rayford").
parent("Margaret Hylton", "Anton Hylton").
parent("Margaret Hylton", "Deirdre Hylton").
parent("Marlana Rayford", "Farrah Moyer").
parent("Marlana Rayford", "Steve Moyer").
parent("Miki Green", "Jacquline Moyer").
parent("Miki Green", "Mack Moyer").
parent("Victoria Eddings", "Jacquline Moyer").
parent("Victoria Eddings", "Mack Moyer").
parent("Aimee Townley", "Monika Townley").
parent("Aimee Townley", "Wilfredo Townley").
parent("Antonio Mello", "Enid Mello").
parent("Antonio Mello", "Jerrold Mello").
parent("Benito Mello", "Edison Mello").
parent("Benito Mello", "Tamala Mello").
parent("Cory Townley", "Monika Townley").
parent("Cory Townley", "Wilfredo Townley").
parent("Edison Mello", "Enid Mello").
parent("Edison Mello", "Jerrold Mello").
parent("Enid Mello", "Esperanza Molnar").
parent("Enid Mello", "Forrest Molnar").
parent("Harriette Mello", "Monika Townley").
parent("Harriette Mello", "Wilfredo Townley").
parent("Irvin Batista", "Hans Batista").
parent("Irvin Batista", "Nydia Batista").
parent("Janey Townley", "Monika Townley").
parent("Janey Townley", "Wilfredo Townley").
parent("Jerrold Mello", "Harriette Mello").
parent("Jerrold Mello", "Tod Mello").
parent("Marcelino Townley", "Monika Townley").
parent("Marcelino Townley", "Wilfredo Townley").
parent("Nydia Batista", "Antonio Mello").
parent("Nydia Batista", "Golda Mello").
parent("Orville Mello", "Enid Mello").
parent("Orville Mello", "Jerrold Mello").
parent("Ramiro Mello", "Edison Mello").
parent("Ramiro Mello", "Tamala Mello").
parent("Roberto Townley", "Cory Townley").
parent("Roberto Townley", "Tiffany Townley").
parent("Rudolf Mello", "Enid Mello").
parent("Rudolf Mello", "Jerrold Mello").

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

gender("Angelo Hylton", "male").
gender("Anton Hylton", "male").
gender("Cristopher Shiver", "male").
gender("Deirdre Hylton", "female").
gender("Dewitt Eddings", "male").
gender("Dick Rayford", "male").
gender("Dominique Moyer", "female").
gender("Eduardo Moyer", "male").
gender("Farrah Moyer", "female").
gender("Jacquline Moyer", "female").
gender("Janis Moyer", "female").
gender("Jeanette Moyer", "female").
gender("Jesus Green", "male").
gender("Jimmie Hylton", "male").
gender("Joaquin Eddings", "male").
gender("Kacey Green", "female").
gender("Mack Moyer", "male").
gender("Mammie Rayford", "female").
gender("Margaret Hylton", "female").
gender("Marlana Rayford", "female").
gender("Miki Green", "female").
gender("Nelly Alanis", "female").
gender("Pasquale Alanis", "male").
gender("Steve Moyer", "male").
gender("Victoria Eddings", "female").
gender("Virgina Shiver", "female").
gender("Aimee Townley", "female").
gender("Antonio Mello", "male").
gender("Benito Mello", "male").
gender("Cory Townley", "male").
gender("Edison Mello", "male").
gender("Enid Mello", "female").
gender("Esperanza Molnar", "female").
gender("Forrest Molnar", "male").
gender("Golda Mello", "female").
gender("Hans Batista", "male").
gender("Harriette Mello", "female").
gender("Irvin Batista", "male").
gender("Janey Townley", "female").
gender("Jerrold Mello", "male").
gender("Marcelino Townley", "male").
gender("Monika Townley", "female").
gender("Nydia Batista", "female").
gender("Orville Mello", "male").
gender("Ramiro Mello", "male").
gender("Roberto Townley", "male").
gender("Rudolf Mello", "male").
gender("Tamala Mello", "female").
gender("Tiffany Townley", "female").
gender("Tod Mello", "male").
gender("Wilfredo Townley", "male").

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

friend_("Angelo Hylton", "Dick Rayford").
friend_("Anton Hylton", "Cory Townley").
friend_("Anton Hylton", "Enid Mello").
friend_("Cristopher Shiver", "Benito Mello").
friend_("Cristopher Shiver", "Nydia Batista").
friend_("Cristopher Shiver", "Tiffany Townley").
friend_("Dewitt Eddings", "Janis Moyer").
friend_("Dewitt Eddings", "Benito Mello").
friend_("Dewitt Eddings", "Wilfredo Townley").
friend_("Dick Rayford", "Pasquale Alanis").
friend_("Dick Rayford", "Steve Moyer").
friend_("Dick Rayford", "Janey Townley").
friend_("Dominique Moyer", "Joaquin Eddings").
friend_("Eduardo Moyer", "Jeanette Moyer").
friend_("Eduardo Moyer", "Kacey Green").
friend_("Eduardo Moyer", "Aimee Townley").
friend_("Eduardo Moyer", "Edison Mello").
friend_("Eduardo Moyer", "Irvin Batista").
friend_("Eduardo Moyer", "Rudolf Mello").
friend_("Farrah Moyer", "Miki Green").
friend_("Jacquline Moyer", "Benito Mello").
friend_("Jacquline Moyer", "Enid Mello").
friend_("Jacquline Moyer", "Esperanza Molnar").
friend_("Janis Moyer", "Victoria Eddings").
friend_("Janis Moyer", "Harriette Mello").
friend_("Janis Moyer", "Tiffany Townley").
friend_("Jeanette Moyer", "Forrest Molnar").
friend_("Jimmie Hylton", "Hans Batista").
friend_("Joaquin Eddings", "Nelly Alanis").
friend_("Joaquin Eddings", "Virgina Shiver").
friend_("Joaquin Eddings", "Irvin Batista").
friend_("Kacey Green", "Benito Mello").
friend_("Mack Moyer", "Miki Green").
friend_("Mack Moyer", "Harriette Mello").
friend_("Mack Moyer", "Orville Mello").
friend_("Mack Moyer", "Tamala Mello").
friend_("Mammie Rayford", "Forrest Molnar").
friend_("Margaret Hylton", "Benito Mello").
friend_("Margaret Hylton", "Rudolf Mello").
friend_("Marlana Rayford", "Roberto Townley").
friend_("Marlana Rayford", "Rudolf Mello").
friend_("Miki Green", "Pasquale Alanis").
friend_("Miki Green", "Janey Townley").
friend_("Miki Green", "Monika Townley").
friend_("Miki Green", "Orville Mello").
friend_("Miki Green", "Ramiro Mello").
friend_("Nelly Alanis", "Monika Townley").
friend_("Nelly Alanis", "Tiffany Townley").
friend_("Pasquale Alanis", "Aimee Townley").
friend_("Pasquale Alanis", "Antonio Mello").
friend_("Pasquale Alanis", "Edison Mello").
friend_("Pasquale Alanis", "Rudolf Mello").
friend_("Steve Moyer", "Aimee Townley").
friend_("Victoria Eddings", "Rudolf Mello").
friend_("Antonio Mello", "Tamala Mello").
friend_("Benito Mello", "Golda Mello").
friend_("Cory Townley", "Nydia Batista").
friend_("Edison Mello", "Esperanza Molnar").
friend_("Edison Mello", "Marcelino Townley").
friend_("Enid Mello", "Tamala Mello").
friend_("Esperanza Molnar", "Harriette Mello").
friend_("Esperanza Molnar", "Tiffany Townley").
friend_("Forrest Molnar", "Ramiro Mello").
friend_("Harriette Mello", "Roberto Townley").
friend_("Irvin Batista", "Monika Townley").
friend_("Irvin Batista", "Tod Mello").
friend_("Janey Townley", "Tamala Mello").
friend_("Janey Townley", "Tod Mello").
friend_("Jerrold Mello", "Roberto Townley").
friend_("Orville Mello", "Tamala Mello").
friend_("Tiffany Townley", "Tod Mello").
friend_("Tod Mello", "Wilfredo Townley").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("training and development officer").
attribute("audiophile").
attribute("financial manager").
attribute("travel").
attribute("TEFL teacher").
attribute("fossil hunting").
attribute("accounting technician").
attribute("microscopy").
attribute("armed forces logistics officer").
attribute("herping").
attribute("energy engineer").
attribute("wikipedia editing").
attribute("early years teacher").
attribute("billiards").
attribute("homeopath").
attribute("satellite watching").
attribute("programme researcher").
attribute("horseshoes").
attribute("mechanical engineer").
attribute("frisbee").
attribute("clinical molecular geneticist").
attribute("video gaming").
attribute("firefighter").
attribute("coin collecting").
attribute("investment analyst").
attribute("mineral collecting").
attribute("public librarian").
attribute("martial arts").
attribute("network engineer").
attribute("kayaking").
attribute("film editor").
attribute("meteorology").
attribute("architect").
attribute("shoes").
attribute("dramatherapist").
attribute("flower collecting and pressing").
attribute("homeopath").
attribute("gongoozling").
attribute("building control surveyor").
attribute("sea glass collecting").
attribute("art gallery manager").
attribute("neuroscience").
attribute("exercise physiologist").
attribute("audiophile").
attribute("scientist").
attribute("research").
attribute("bonds trader").
attribute("gongoozling").
attribute("artist").
attribute("astronomy").
attribute("printmaker").
attribute("research").
attribute("field seismologist").
attribute("metal detecting").
attribute("film editor").
attribute("leaves").
attribute("English as a second language teacher").
attribute("shortwave listening").
attribute("clothing technologist").
attribute("flower collecting and pressing").
attribute("computer games developer").
attribute("urban exploration").
attribute("field seismologist").
attribute("magnet fishing").
attribute("chief marketing officer").
attribute("perfume").
attribute("product development scientist").
attribute("high-power rocketry").
attribute("chemist").
attribute("ice hockey").
attribute("pensions consultant").
attribute("gongoozling").
attribute("psychologist").
attribute("audiophile").
attribute("records manager").
attribute("esports").
attribute("translator").
attribute("poker").
attribute("financial controller").
attribute("snowboarding").
attribute("fast food restaurant manager").
attribute("baton twirling").
attribute("health promotion specialist").
attribute("aerospace").
attribute("training and development officer").
attribute("films").
attribute("surgeon").
attribute("insect collecting").
attribute("patent examiner").
attribute("herping").
attribute("data processing manager").
attribute("debate").
attribute("chiropractor").
attribute("chess").
attribute("quality manager").
attribute("disc golf").
attribute("herbalist").
attribute("cycling").
attribute("plant breeder").
attribute("martial arts").
attribute("waste management officer").
attribute("learning").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Angelo Hylton", person).
type("Anton Hylton", person).
type("Cristopher Shiver", person).
type("Deirdre Hylton", person).
type("Dewitt Eddings", person).
type("Dick Rayford", person).
type("Dominique Moyer", person).
type("Eduardo Moyer", person).
type("Farrah Moyer", person).
type("Jacquline Moyer", person).
type("Janis Moyer", person).
type("Jeanette Moyer", person).
type("Jesus Green", person).
type("Jimmie Hylton", person).
type("Joaquin Eddings", person).
type("Kacey Green", person).
type("Mack Moyer", person).
type("Mammie Rayford", person).
type("Margaret Hylton", person).
type("Marlana Rayford", person).
type("Miki Green", person).
type("Nelly Alanis", person).
type("Pasquale Alanis", person).
type("Steve Moyer", person).
type("Victoria Eddings", person).
type("Virgina Shiver", person).
type("Aimee Townley", person).
type("Antonio Mello", person).
type("Benito Mello", person).
type("Cory Townley", person).
type("Edison Mello", person).
type("Enid Mello", person).
type("Esperanza Molnar", person).
type("Forrest Molnar", person).
type("Golda Mello", person).
type("Hans Batista", person).
type("Harriette Mello", person).
type("Irvin Batista", person).
type("Janey Townley", person).
type("Jerrold Mello", person).
type("Marcelino Townley", person).
type("Monika Townley", person).
type("Nydia Batista", person).
type("Orville Mello", person).
type("Ramiro Mello", person).
type("Roberto Townley", person).
type("Rudolf Mello", person).
type("Tamala Mello", person).
type("Tiffany Townley", person).
type("Tod Mello", person).
type("Wilfredo Townley", person).

:- dynamic dob/2.

dob("Angelo Hylton", "0207-06-08").
dob("Anton Hylton", "0177-01-17").
dob("Cristopher Shiver", "0228-07-19").
dob("Deirdre Hylton", "0175-01-15").
dob("Dewitt Eddings", "0310-09-04").
dob("Dick Rayford", "0225-09-07").
dob("Dominique Moyer", "0232-08-04").
dob("Eduardo Moyer", "0233-01-11").
dob("Farrah Moyer", "0202-06-17").
dob("Jacquline Moyer", "0259-10-11").
dob("Janis Moyer", "0234-08-16").
dob("Jeanette Moyer", "0257-09-23").
dob("Jesus Green", "0290-05-21").
dob("Jimmie Hylton", "0207-11-19").
dob("Joaquin Eddings", "0281-08-03").
dob("Kacey Green", "0315-03-02").
dob("Mack Moyer", "0261-07-18").
dob("Mammie Rayford", "0261-07-01").
dob("Margaret Hylton", "0202-04-03").
dob("Marlana Rayford", "0228-02-23").
dob("Miki Green", "0290-12-24").
dob("Nelly Alanis", "0211-05-26").
dob("Pasquale Alanis", "0207-09-02").
dob("Steve Moyer", "0203-08-15").
dob("Victoria Eddings", "0285-08-05").
dob("Virgina Shiver", "0229-06-22").
dob("Aimee Townley", "0203-12-15").
dob("Antonio Mello", "0283-04-05").
dob("Benito Mello", "0306-11-27").
dob("Cory Townley", "0206-10-09").
dob("Edison Mello", "0275-03-18").
dob("Enid Mello", "0250-12-17").
dob("Esperanza Molnar", "0218-11-03").
dob("Forrest Molnar", "0219-03-06").
dob("Golda Mello", "0284-08-23").
dob("Hans Batista", "0308-10-19").
dob("Harriette Mello", "0213-09-17").
dob("Irvin Batista", "0337-11-17").
dob("Janey Townley", "0216-07-24").
dob("Jerrold Mello", "0246-01-26").
dob("Marcelino Townley", "0210-02-04").
dob("Monika Townley", "0184-06-22").
dob("Nydia Batista", "0309-09-12").
dob("Orville Mello", "0276-01-06").
dob("Ramiro Mello", "0303-03-29").
dob("Roberto Townley", "0232-04-27").
dob("Rudolf Mello", "0279-08-28").
dob("Tamala Mello", "0277-02-03").
dob("Tiffany Townley", "0203-07-18").
dob("Tod Mello", "0215-07-14").
dob("Wilfredo Townley", "0182-11-20").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Angelo Hylton", "training and development officer").
job("Anton Hylton", "financial manager").
job("Cristopher Shiver", "TEFL teacher").
job("Deirdre Hylton", "accounting technician").
job("Dewitt Eddings", "armed forces logistics officer").
job("Dick Rayford", "energy engineer").
job("Dominique Moyer", "early years teacher").
job("Eduardo Moyer", "homeopath").
job("Farrah Moyer", "programme researcher").
job("Jacquline Moyer", "mechanical engineer").
job("Janis Moyer", "clinical molecular geneticist").
job("Jeanette Moyer", "firefighter").
job("Jesus Green", "investment analyst").
job("Jimmie Hylton", "public librarian").
job("Joaquin Eddings", "network engineer").
job("Kacey Green", "film editor").
job("Mack Moyer", "architect").
job("Mammie Rayford", "dramatherapist").
job("Margaret Hylton", "homeopath").
job("Marlana Rayford", "building control surveyor").
job("Miki Green", "art gallery manager").
job("Nelly Alanis", "exercise physiologist").
job("Pasquale Alanis", "scientist").
job("Steve Moyer", "bonds trader").
job("Victoria Eddings", "artist").
job("Virgina Shiver", "printmaker").
job("Aimee Townley", "field seismologist").
job("Antonio Mello", "film editor").
job("Benito Mello", "English as a second language teacher").
job("Cory Townley", "clothing technologist").
job("Edison Mello", "computer games developer").
job("Enid Mello", "field seismologist").
job("Esperanza Molnar", "chief marketing officer").
job("Forrest Molnar", "product development scientist").
job("Golda Mello", "chemist").
job("Hans Batista", "pensions consultant").
job("Harriette Mello", "psychologist").
job("Irvin Batista", "records manager").
job("Janey Townley", "translator").
job("Jerrold Mello", "financial controller").
job("Marcelino Townley", "fast food restaurant manager").
job("Monika Townley", "health promotion specialist").
job("Nydia Batista", "training and development officer").
job("Orville Mello", "surgeon").
job("Ramiro Mello", "patent examiner").
job("Roberto Townley", "data processing manager").
job("Rudolf Mello", "chiropractor").
job("Tamala Mello", "quality manager").
job("Tiffany Townley", "herbalist").
job("Tod Mello", "plant breeder").
job("Wilfredo Townley", "waste management officer").

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

hobby("Angelo Hylton", "audiophile").
hobby("Anton Hylton", "travel").
hobby("Cristopher Shiver", "fossil hunting").
hobby("Deirdre Hylton", "microscopy").
hobby("Dewitt Eddings", "herping").
hobby("Dick Rayford", "wikipedia editing").
hobby("Dominique Moyer", "billiards").
hobby("Eduardo Moyer", "satellite watching").
hobby("Farrah Moyer", "horseshoes").
hobby("Jacquline Moyer", "frisbee").
hobby("Janis Moyer", "video gaming").
hobby("Jeanette Moyer", "coin collecting").
hobby("Jesus Green", "mineral collecting").
hobby("Jimmie Hylton", "martial arts").
hobby("Joaquin Eddings", "kayaking").
hobby("Kacey Green", "meteorology").
hobby("Mack Moyer", "shoes").
hobby("Mammie Rayford", "flower collecting and pressing").
hobby("Margaret Hylton", "gongoozling").
hobby("Marlana Rayford", "sea glass collecting").
hobby("Miki Green", "neuroscience").
hobby("Nelly Alanis", "audiophile").
hobby("Pasquale Alanis", "research").
hobby("Steve Moyer", "gongoozling").
hobby("Victoria Eddings", "astronomy").
hobby("Virgina Shiver", "research").
hobby("Aimee Townley", "metal detecting").
hobby("Antonio Mello", "leaves").
hobby("Benito Mello", "shortwave listening").
hobby("Cory Townley", "flower collecting and pressing").
hobby("Edison Mello", "urban exploration").
hobby("Enid Mello", "magnet fishing").
hobby("Esperanza Molnar", "perfume").
hobby("Forrest Molnar", "high-power rocketry").
hobby("Golda Mello", "ice hockey").
hobby("Hans Batista", "gongoozling").
hobby("Harriette Mello", "audiophile").
hobby("Irvin Batista", "esports").
hobby("Janey Townley", "poker").
hobby("Jerrold Mello", "snowboarding").
hobby("Marcelino Townley", "baton twirling").
hobby("Monika Townley", "aerospace").
hobby("Nydia Batista", "films").
hobby("Orville Mello", "insect collecting").
hobby("Ramiro Mello", "herping").
hobby("Roberto Townley", "debate").
hobby("Rudolf Mello", "chess").
hobby("Tamala Mello", "disc golf").
hobby("Tiffany Townley", "cycling").
hobby("Tod Mello", "martial arts").
hobby("Wilfredo Townley", "learning").

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
