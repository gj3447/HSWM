
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

parent("Adalberto Oster", "Dylan Oster").
parent("Adalberto Oster", "Pamula Oster").
parent("Anibal Lawhorn", "Brooks Lawhorn").
parent("Anibal Lawhorn", "Lauren Lawhorn").
parent("Babette Farmer", "Brooks Lawhorn").
parent("Babette Farmer", "Lauren Lawhorn").
parent("Bethany Lawhorn", "Chante Lawhorn").
parent("Bethany Lawhorn", "Quintin Lawhorn").
parent("Brooks Lawhorn", "Geoffrey Lawhorn").
parent("Brooks Lawhorn", "Niesha Lawhorn").
parent("Cheri Lawhorn", "Olin Lawhorn").
parent("Cheri Lawhorn", "Tiesha Lawhorn").
parent("Cliff Farmer", "Babette Farmer").
parent("Cliff Farmer", "Chris Farmer").
parent("Elicia Mcreynolds", "Edmundo Mcreynolds").
parent("Elicia Mcreynolds", "Thalia Mcreynolds").
parent("Ervin Nagy", "Douglas Nagy").
parent("Ervin Nagy", "Leeanne Nagy").
parent("Geoffrey Lawhorn", "Olin Lawhorn").
parent("Geoffrey Lawhorn", "Tiesha Lawhorn").
parent("Isidro Lawhorn", "Brooks Lawhorn").
parent("Isidro Lawhorn", "Lauren Lawhorn").
parent("Leeanne Nagy", "Geoffrey Lawhorn").
parent("Leeanne Nagy", "Niesha Lawhorn").
parent("Oma Lawhorn", "Olin Lawhorn").
parent("Oma Lawhorn", "Tiesha Lawhorn").
parent("Pamula Oster", "Geoffrey Lawhorn").
parent("Pamula Oster", "Niesha Lawhorn").
parent("Quintin Lawhorn", "Olin Lawhorn").
parent("Quintin Lawhorn", "Tiesha Lawhorn").
parent("Romona Lawhorn", "Chante Lawhorn").
parent("Romona Lawhorn", "Quintin Lawhorn").
parent("Thalia Mcreynolds", "Geoffrey Lawhorn").
parent("Thalia Mcreynolds", "Niesha Lawhorn").
parent("Adrienne Clapper", "Charity Clapper").
parent("Adrienne Clapper", "Christopher Clapper").
parent("Art Clapper", "Marlena Clapper").
parent("Art Clapper", "Tomas Clapper").
parent("Charity Clapper", "Kacey Joiner").
parent("Charity Clapper", "Riley Joiner").
parent("Christopher Clapper", "Marlena Clapper").
parent("Christopher Clapper", "Tomas Clapper").
parent("Claude Clapper", "Charity Clapper").
parent("Claude Clapper", "Christopher Clapper").
parent("Danilo Clapper", "Marlena Clapper").
parent("Danilo Clapper", "Tomas Clapper").
parent("Delbert Avila", "Brendon Avila").
parent("Delbert Avila", "Vilma Avila").
parent("Haywood Clapper", "Marlena Clapper").
parent("Haywood Clapper", "Tomas Clapper").
parent("Jarvis Clapper", "Kraig Clapper").
parent("Jarvis Clapper", "Sondra Clapper").
parent("Kimiko Avila", "Brendon Avila").
parent("Kimiko Avila", "Vilma Avila").
parent("Lora Avila", "Ashton Kersey").
parent("Lora Avila", "Bradley Kersey").
parent("Mariana Avila", "Delbert Avila").
parent("Mariana Avila", "Lora Avila").
parent("Riley Clapper", "Charity Clapper").
parent("Riley Clapper", "Christopher Clapper").
parent("Timothy Clapper", "Haywood Clapper").
parent("Timothy Clapper", "Heidi Clapper").
parent("Tomas Clapper", "Kraig Clapper").
parent("Tomas Clapper", "Sondra Clapper").
parent("Vilma Avila", "Marlena Clapper").
parent("Vilma Avila", "Tomas Clapper").

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

gender("Adalberto Oster", "male").
gender("Anibal Lawhorn", "male").
gender("Babette Farmer", "female").
gender("Bethany Lawhorn", "female").
gender("Brooks Lawhorn", "male").
gender("Chante Lawhorn", "female").
gender("Cheri Lawhorn", "female").
gender("Chris Farmer", "male").
gender("Cliff Farmer", "male").
gender("Douglas Nagy", "male").
gender("Dylan Oster", "male").
gender("Edmundo Mcreynolds", "male").
gender("Elicia Mcreynolds", "female").
gender("Ervin Nagy", "male").
gender("Geoffrey Lawhorn", "male").
gender("Isidro Lawhorn", "male").
gender("Lauren Lawhorn", "female").
gender("Leeanne Nagy", "female").
gender("Niesha Lawhorn", "female").
gender("Olin Lawhorn", "male").
gender("Oma Lawhorn", "female").
gender("Pamula Oster", "female").
gender("Quintin Lawhorn", "male").
gender("Romona Lawhorn", "female").
gender("Thalia Mcreynolds", "female").
gender("Tiesha Lawhorn", "female").
gender("Adrienne Clapper", "female").
gender("Art Clapper", "male").
gender("Ashton Kersey", "female").
gender("Bradley Kersey", "male").
gender("Brendon Avila", "male").
gender("Charity Clapper", "female").
gender("Christopher Clapper", "male").
gender("Claude Clapper", "male").
gender("Danilo Clapper", "male").
gender("Delbert Avila", "male").
gender("Haywood Clapper", "male").
gender("Heidi Clapper", "female").
gender("Jarvis Clapper", "male").
gender("Kacey Joiner", "female").
gender("Kimiko Avila", "female").
gender("Kraig Clapper", "male").
gender("Lora Avila", "female").
gender("Mariana Avila", "female").
gender("Marlena Clapper", "female").
gender("Riley Clapper", "male").
gender("Riley Joiner", "male").
gender("Sondra Clapper", "female").
gender("Timothy Clapper", "male").
gender("Tomas Clapper", "male").
gender("Vilma Avila", "female").

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

friend_("Adalberto Oster", "Leeanne Nagy").
friend_("Adalberto Oster", "Art Clapper").
friend_("Adalberto Oster", "Bradley Kersey").
friend_("Anibal Lawhorn", "Leeanne Nagy").
friend_("Anibal Lawhorn", "Thalia Mcreynolds").
friend_("Anibal Lawhorn", "Delbert Avila").
friend_("Anibal Lawhorn", "Haywood Clapper").
friend_("Anibal Lawhorn", "Riley Joiner").
friend_("Babette Farmer", "Chante Lawhorn").
friend_("Babette Farmer", "Geoffrey Lawhorn").
friend_("Babette Farmer", "Niesha Lawhorn").
friend_("Babette Farmer", "Lora Avila").
friend_("Bethany Lawhorn", "Quintin Lawhorn").
friend_("Bethany Lawhorn", "Danilo Clapper").
friend_("Bethany Lawhorn", "Mariana Avila").
friend_("Brooks Lawhorn", "Tiesha Lawhorn").
friend_("Brooks Lawhorn", "Kraig Clapper").
friend_("Brooks Lawhorn", "Tomas Clapper").
friend_("Chante Lawhorn", "Quintin Lawhorn").
friend_("Chante Lawhorn", "Art Clapper").
friend_("Chante Lawhorn", "Sondra Clapper").
friend_("Cheri Lawhorn", "Elicia Mcreynolds").
friend_("Cheri Lawhorn", "Thalia Mcreynolds").
friend_("Chris Farmer", "Bradley Kersey").
friend_("Chris Farmer", "Lora Avila").
friend_("Cliff Farmer", "Ashton Kersey").
friend_("Cliff Farmer", "Charity Clapper").
friend_("Cliff Farmer", "Haywood Clapper").
friend_("Cliff Farmer", "Heidi Clapper").
friend_("Cliff Farmer", "Timothy Clapper").
friend_("Douglas Nagy", "Pamula Oster").
friend_("Douglas Nagy", "Thalia Mcreynolds").
friend_("Douglas Nagy", "Riley Clapper").
friend_("Douglas Nagy", "Riley Joiner").
friend_("Dylan Oster", "Edmundo Mcreynolds").
friend_("Dylan Oster", "Thalia Mcreynolds").
friend_("Dylan Oster", "Christopher Clapper").
friend_("Dylan Oster", "Kraig Clapper").
friend_("Elicia Mcreynolds", "Quintin Lawhorn").
friend_("Elicia Mcreynolds", "Kraig Clapper").
friend_("Ervin Nagy", "Olin Lawhorn").
friend_("Ervin Nagy", "Quintin Lawhorn").
friend_("Ervin Nagy", "Thalia Mcreynolds").
friend_("Ervin Nagy", "Adrienne Clapper").
friend_("Ervin Nagy", "Kraig Clapper").
friend_("Ervin Nagy", "Riley Joiner").
friend_("Geoffrey Lawhorn", "Delbert Avila").
friend_("Isidro Lawhorn", "Thalia Mcreynolds").
friend_("Lauren Lawhorn", "Adrienne Clapper").
friend_("Lauren Lawhorn", "Kraig Clapper").
friend_("Lauren Lawhorn", "Mariana Avila").
friend_("Leeanne Nagy", "Romona Lawhorn").
friend_("Leeanne Nagy", "Brendon Avila").
friend_("Leeanne Nagy", "Kimiko Avila").
friend_("Niesha Lawhorn", "Ashton Kersey").
friend_("Niesha Lawhorn", "Danilo Clapper").
friend_("Olin Lawhorn", "Delbert Avila").
friend_("Olin Lawhorn", "Heidi Clapper").
friend_("Olin Lawhorn", "Kimiko Avila").
friend_("Olin Lawhorn", "Marlena Clapper").
friend_("Olin Lawhorn", "Tomas Clapper").
friend_("Oma Lawhorn", "Thalia Mcreynolds").
friend_("Pamula Oster", "Adrienne Clapper").
friend_("Quintin Lawhorn", "Charity Clapper").
friend_("Quintin Lawhorn", "Delbert Avila").
friend_("Thalia Mcreynolds", "Delbert Avila").
friend_("Tiesha Lawhorn", "Tomas Clapper").
friend_("Adrienne Clapper", "Kraig Clapper").
friend_("Adrienne Clapper", "Marlena Clapper").
friend_("Art Clapper", "Brendon Avila").
friend_("Art Clapper", "Danilo Clapper").
friend_("Ashton Kersey", "Christopher Clapper").
friend_("Bradley Kersey", "Riley Clapper").
friend_("Brendon Avila", "Timothy Clapper").
friend_("Christopher Clapper", "Heidi Clapper").
friend_("Claude Clapper", "Haywood Clapper").
friend_("Danilo Clapper", "Kacey Joiner").
friend_("Delbert Avila", "Jarvis Clapper").
friend_("Delbert Avila", "Mariana Avila").
friend_("Delbert Avila", "Marlena Clapper").
friend_("Haywood Clapper", "Marlena Clapper").
friend_("Jarvis Clapper", "Mariana Avila").
friend_("Mariana Avila", "Riley Clapper").
friend_("Marlena Clapper", "Riley Joiner").
friend_("Riley Joiner", "Tomas Clapper").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("counsellor").
attribute("billiards").
attribute("pensions consultant").
attribute("research").
attribute("management consultant").
attribute("flower collecting and pressing").
attribute("theatre stage manager").
attribute("wikipedia editing").
attribute("water quality scientist").
attribute("weightlifting").
attribute("ship broker").
attribute("stuffed toy collecting").
attribute("speech and language therapist").
attribute("dominoes").
attribute("land surveyor").
attribute("antiquities").
attribute("industrial buyer").
attribute("flower growing").
attribute("land surveyor").
attribute("learning").
attribute("magazine features editor").
attribute("benchmarking").
attribute("psychiatrist").
attribute("benchmarking").
attribute("armed forces training and education officer").
attribute("inline skating").
attribute("graphic designer").
attribute("life science").
attribute("ambulance person").
attribute("speed skating").
attribute("surgeon").
attribute("sport stacking").
attribute("historic buildings inspector").
attribute("fingerprint collecting").
attribute("hydrogeologist").
attribute("dolls").
attribute("set designer").
attribute("fossil hunting").
attribute("chief strategy officer").
attribute("research").
attribute("geologist").
attribute("pinball").
attribute("control and instrumentation engineer").
attribute("reading").
attribute("environmental health practitioner").
attribute("fishkeeping").
attribute("civil service fast streamer").
attribute("insect collecting").
attribute("risk analyst").
attribute("bus spotting").
attribute("phytotherapist").
attribute("equestrianism").
attribute("hospital doctor").
attribute("axe throwing").
attribute("commercial art gallery manager").
attribute("learning").
attribute("animal nutritionist").
attribute("birdwatching").
attribute("public relations officer").
attribute("fishkeeping").
attribute("holiday representative").
attribute("trade fair visiting").
attribute("musician").
attribute("ballroom dancing").
attribute("forensic psychologist").
attribute("sled dog racing").
attribute("prison officer").
attribute("ticket collecting").
attribute("sports administrator").
attribute("entrepreneurship").
attribute("dance movement psychotherapist").
attribute("architecture").
attribute("comptroller").
attribute("table football").
attribute("make").
attribute("ant-keeping").
attribute("chief financial officer").
attribute("fitness").
attribute("wellsite geologist").
attribute("breakdancing").
attribute("television floor manager").
attribute("auto detailing").
attribute("clinical embryologist").
attribute("longboarding").
attribute("tree surgeon").
attribute("comic book collecting").
attribute("conservator").
attribute("architecture").
attribute("medical sales representative").
attribute("ant farming").
attribute("building services engineer").
attribute("book folding").
attribute("water quality scientist").
attribute("shortwave listening").
attribute("acupuncturist").
attribute("knife collecting").
attribute("surveyor").
attribute("research").
attribute("art therapist").
attribute("knowledge/word games").
attribute("government social research officer").
attribute("comic book collecting").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adalberto Oster", person).
type("Anibal Lawhorn", person).
type("Babette Farmer", person).
type("Bethany Lawhorn", person).
type("Brooks Lawhorn", person).
type("Chante Lawhorn", person).
type("Cheri Lawhorn", person).
type("Chris Farmer", person).
type("Cliff Farmer", person).
type("Douglas Nagy", person).
type("Dylan Oster", person).
type("Edmundo Mcreynolds", person).
type("Elicia Mcreynolds", person).
type("Ervin Nagy", person).
type("Geoffrey Lawhorn", person).
type("Isidro Lawhorn", person).
type("Lauren Lawhorn", person).
type("Leeanne Nagy", person).
type("Niesha Lawhorn", person).
type("Olin Lawhorn", person).
type("Oma Lawhorn", person).
type("Pamula Oster", person).
type("Quintin Lawhorn", person).
type("Romona Lawhorn", person).
type("Thalia Mcreynolds", person).
type("Tiesha Lawhorn", person).
type("Adrienne Clapper", person).
type("Art Clapper", person).
type("Ashton Kersey", person).
type("Bradley Kersey", person).
type("Brendon Avila", person).
type("Charity Clapper", person).
type("Christopher Clapper", person).
type("Claude Clapper", person).
type("Danilo Clapper", person).
type("Delbert Avila", person).
type("Haywood Clapper", person).
type("Heidi Clapper", person).
type("Jarvis Clapper", person).
type("Kacey Joiner", person).
type("Kimiko Avila", person).
type("Kraig Clapper", person).
type("Lora Avila", person).
type("Mariana Avila", person).
type("Marlena Clapper", person).
type("Riley Clapper", person).
type("Riley Joiner", person).
type("Sondra Clapper", person).
type("Timothy Clapper", person).
type("Tomas Clapper", person).
type("Vilma Avila", person).

:- dynamic dob/2.

dob("Adalberto Oster", "0288-08-13").
dob("Anibal Lawhorn", "0290-02-18").
dob("Babette Farmer", "0291-01-17").
dob("Bethany Lawhorn", "0265-12-10").
dob("Brooks Lawhorn", "0264-08-11").
dob("Chante Lawhorn", "0238-12-07").
dob("Cheri Lawhorn", "0240-03-30").
dob("Chris Farmer", "0292-08-09").
dob("Cliff Farmer", "0322-01-24").
dob("Douglas Nagy", "0264-06-02").
dob("Dylan Oster", "0263-05-08").
dob("Edmundo Mcreynolds", "0261-12-18").
dob("Elicia Mcreynolds", "0294-06-14").
dob("Ervin Nagy", "0292-03-15").
dob("Geoffrey Lawhorn", "0236-11-19").
dob("Isidro Lawhorn", "0298-01-09").
dob("Lauren Lawhorn", "0260-05-08").
dob("Leeanne Nagy", "0266-08-23").
dob("Niesha Lawhorn", "0234-02-19").
dob("Olin Lawhorn", "0210-10-11").
dob("Oma Lawhorn", "0239-02-04").
dob("Pamula Oster", "0263-04-13").
dob("Quintin Lawhorn", "0242-02-08").
dob("Romona Lawhorn", "0270-07-31").
dob("Thalia Mcreynolds", "0263-04-13").
dob("Tiesha Lawhorn", "0211-11-14").
dob("Adrienne Clapper", "0289-12-10").
dob("Art Clapper", "0265-05-07").
dob("Ashton Kersey", "0256-09-18").
dob("Bradley Kersey", "0257-11-25").
dob("Brendon Avila", "0259-10-08").
dob("Charity Clapper", "0261-02-10").
dob("Christopher Clapper", "0264-06-23").
dob("Claude Clapper", "0287-08-28").
dob("Danilo Clapper", "0267-08-29").
dob("Delbert Avila", "0288-08-23").
dob("Haywood Clapper", "0266-01-25").
dob("Heidi Clapper", "0267-01-02").
dob("Jarvis Clapper", "0232-09-04").
dob("Kacey Joiner", "0229-03-06").
dob("Kimiko Avila", "0290-01-27").
dob("Kraig Clapper", "0210-01-28").
dob("Lora Avila", "0289-02-11").
dob("Mariana Avila", "0316-11-12").
dob("Marlena Clapper", "0237-07-26").
dob("Riley Clapper", "0290-10-28").
dob("Riley Joiner", "0231-04-01").
dob("Sondra Clapper", "0209-01-05").
dob("Timothy Clapper", "0293-06-27").
dob("Tomas Clapper", "0237-02-26").
dob("Vilma Avila", "0261-09-07").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adalberto Oster", "counsellor").
job("Anibal Lawhorn", "pensions consultant").
job("Babette Farmer", "management consultant").
job("Bethany Lawhorn", "theatre stage manager").
job("Brooks Lawhorn", "water quality scientist").
job("Chante Lawhorn", "ship broker").
job("Cheri Lawhorn", "speech and language therapist").
job("Chris Farmer", "land surveyor").
job("Cliff Farmer", "industrial buyer").
job("Douglas Nagy", "land surveyor").
job("Dylan Oster", "magazine features editor").
job("Edmundo Mcreynolds", "psychiatrist").
job("Elicia Mcreynolds", "armed forces training and education officer").
job("Ervin Nagy", "graphic designer").
job("Geoffrey Lawhorn", "ambulance person").
job("Isidro Lawhorn", "surgeon").
job("Lauren Lawhorn", "historic buildings inspector").
job("Leeanne Nagy", "hydrogeologist").
job("Niesha Lawhorn", "set designer").
job("Olin Lawhorn", "chief strategy officer").
job("Oma Lawhorn", "geologist").
job("Pamula Oster", "control and instrumentation engineer").
job("Quintin Lawhorn", "environmental health practitioner").
job("Romona Lawhorn", "civil service fast streamer").
job("Thalia Mcreynolds", "risk analyst").
job("Tiesha Lawhorn", "phytotherapist").
job("Adrienne Clapper", "hospital doctor").
job("Art Clapper", "commercial art gallery manager").
job("Ashton Kersey", "animal nutritionist").
job("Bradley Kersey", "public relations officer").
job("Brendon Avila", "holiday representative").
job("Charity Clapper", "musician").
job("Christopher Clapper", "forensic psychologist").
job("Claude Clapper", "prison officer").
job("Danilo Clapper", "sports administrator").
job("Delbert Avila", "dance movement psychotherapist").
job("Haywood Clapper", "comptroller").
job("Heidi Clapper", "make").
job("Jarvis Clapper", "chief financial officer").
job("Kacey Joiner", "wellsite geologist").
job("Kimiko Avila", "television floor manager").
job("Kraig Clapper", "clinical embryologist").
job("Lora Avila", "tree surgeon").
job("Mariana Avila", "conservator").
job("Marlena Clapper", "medical sales representative").
job("Riley Clapper", "building services engineer").
job("Riley Joiner", "water quality scientist").
job("Sondra Clapper", "acupuncturist").
job("Timothy Clapper", "surveyor").
job("Tomas Clapper", "art therapist").
job("Vilma Avila", "government social research officer").

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

hobby("Adalberto Oster", "billiards").
hobby("Anibal Lawhorn", "research").
hobby("Babette Farmer", "flower collecting and pressing").
hobby("Bethany Lawhorn", "wikipedia editing").
hobby("Brooks Lawhorn", "weightlifting").
hobby("Chante Lawhorn", "stuffed toy collecting").
hobby("Cheri Lawhorn", "dominoes").
hobby("Chris Farmer", "antiquities").
hobby("Cliff Farmer", "flower growing").
hobby("Douglas Nagy", "learning").
hobby("Dylan Oster", "benchmarking").
hobby("Edmundo Mcreynolds", "benchmarking").
hobby("Elicia Mcreynolds", "inline skating").
hobby("Ervin Nagy", "life science").
hobby("Geoffrey Lawhorn", "speed skating").
hobby("Isidro Lawhorn", "sport stacking").
hobby("Lauren Lawhorn", "fingerprint collecting").
hobby("Leeanne Nagy", "dolls").
hobby("Niesha Lawhorn", "fossil hunting").
hobby("Olin Lawhorn", "research").
hobby("Oma Lawhorn", "pinball").
hobby("Pamula Oster", "reading").
hobby("Quintin Lawhorn", "fishkeeping").
hobby("Romona Lawhorn", "insect collecting").
hobby("Thalia Mcreynolds", "bus spotting").
hobby("Tiesha Lawhorn", "equestrianism").
hobby("Adrienne Clapper", "axe throwing").
hobby("Art Clapper", "learning").
hobby("Ashton Kersey", "birdwatching").
hobby("Bradley Kersey", "fishkeeping").
hobby("Brendon Avila", "trade fair visiting").
hobby("Charity Clapper", "ballroom dancing").
hobby("Christopher Clapper", "sled dog racing").
hobby("Claude Clapper", "ticket collecting").
hobby("Danilo Clapper", "entrepreneurship").
hobby("Delbert Avila", "architecture").
hobby("Haywood Clapper", "table football").
hobby("Heidi Clapper", "ant-keeping").
hobby("Jarvis Clapper", "fitness").
hobby("Kacey Joiner", "breakdancing").
hobby("Kimiko Avila", "auto detailing").
hobby("Kraig Clapper", "longboarding").
hobby("Lora Avila", "comic book collecting").
hobby("Mariana Avila", "architecture").
hobby("Marlena Clapper", "ant farming").
hobby("Riley Clapper", "book folding").
hobby("Riley Joiner", "shortwave listening").
hobby("Sondra Clapper", "knife collecting").
hobby("Timothy Clapper", "research").
hobby("Tomas Clapper", "knowledge/word games").
hobby("Vilma Avila", "comic book collecting").

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
