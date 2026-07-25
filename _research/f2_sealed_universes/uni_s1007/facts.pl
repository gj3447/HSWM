
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

parent("Ai Schafer", "Emerson Warren").
parent("Ai Schafer", "Maragret Warren").
parent("Alexa Schafer", "Ai Schafer").
parent("Alexa Schafer", "Armando Schafer").
parent("Bess Kirksey", "Frederic Kirksey").
parent("Bess Kirksey", "Maira Kirksey").
parent("Charley Kirkham", "Anneliese Kirkham").
parent("Charley Kirkham", "Shane Kirkham").
parent("Emery Schafer", "Ai Schafer").
parent("Emery Schafer", "Armando Schafer").
parent("Florence Kirkham", "Frederic Kirksey").
parent("Florence Kirkham", "Maira Kirksey").
parent("Floyd Schafer", "Ai Schafer").
parent("Floyd Schafer", "Armando Schafer").
parent("Frederic Kirksey", "Alethia Kirksey").
parent("Frederic Kirksey", "Bryan Kirksey").
parent("Lakeshia Warren", "Keri Warren").
parent("Lakeshia Warren", "Moises Warren").
parent("Maragret Warren", "Frederic Kirksey").
parent("Maragret Warren", "Maira Kirksey").
parent("Moises Warren", "Oscar Warren").
parent("Moises Warren", "Velia Warren").
parent("Oscar Warren", "Emerson Warren").
parent("Oscar Warren", "Maragret Warren").
parent("Rory Kirkham", "Florence Kirkham").
parent("Rory Kirkham", "Vernon Kirkham").
parent("Vernon Kirkham", "Anneliese Kirkham").
parent("Vernon Kirkham", "Shane Kirkham").
parent("Violet Schafer", "Ai Schafer").
parent("Violet Schafer", "Armando Schafer").
parent("Yasmin Schafer", "Ai Schafer").
parent("Yasmin Schafer", "Armando Schafer").
parent("Amy Hunsaker", "Norris Hunsaker").
parent("Amy Hunsaker", "Robbie Hunsaker").
parent("Angel Fudge", "Carter Fudge").
parent("Angel Fudge", "Kristie Fudge").
parent("Anita Fudge", "Jack Summerlin").
parent("Anita Fudge", "Nancy Summerlin").
parent("Augustus Robertson", "Alex Robertson").
parent("Augustus Robertson", "Mavis Robertson").
parent("Brittaney Rowell", "Anita Fudge").
parent("Brittaney Rowell", "Garth Fudge").
parent("Dalton Fudge", "Anita Fudge").
parent("Dalton Fudge", "Garth Fudge").
parent("Daniel Rowell", "Brittaney Rowell").
parent("Daniel Rowell", "Lyle Rowell").
parent("Danielle Banner", "Brittaney Rowell").
parent("Danielle Banner", "Lyle Rowell").
parent("Garth Fudge", "Carter Fudge").
parent("Garth Fudge", "Kristie Fudge").
parent("Helga Robertson", "Brittaney Rowell").
parent("Helga Robertson", "Lyle Rowell").
parent("Ignacio Robertson", "Augustus Robertson").
parent("Ignacio Robertson", "Helga Robertson").
parent("Mavis Robertson", "Freeda Dent").
parent("Mavis Robertson", "Nevin Dent").
parent("Rayna Fudge", "Dalton Fudge").
parent("Rayna Fudge", "Joelle Fudge").
parent("Robbie Hunsaker", "Dalton Fudge").
parent("Robbie Hunsaker", "Joelle Fudge").
parent("Tanya Banner", "Danielle Banner").
parent("Tanya Banner", "Harold Banner").

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

gender("Ai Schafer", "female").
gender("Alethia Kirksey", "female").
gender("Alexa Schafer", "female").
gender("Anneliese Kirkham", "female").
gender("Armando Schafer", "male").
gender("Bess Kirksey", "female").
gender("Bryan Kirksey", "male").
gender("Charley Kirkham", "male").
gender("Emerson Warren", "male").
gender("Emery Schafer", "male").
gender("Florence Kirkham", "female").
gender("Floyd Schafer", "male").
gender("Frederic Kirksey", "male").
gender("Keri Warren", "female").
gender("Lakeshia Warren", "female").
gender("Maira Kirksey", "female").
gender("Maragret Warren", "female").
gender("Moises Warren", "male").
gender("Oscar Warren", "male").
gender("Rory Kirkham", "male").
gender("Shane Kirkham", "male").
gender("Velia Warren", "female").
gender("Vernon Kirkham", "male").
gender("Violet Schafer", "female").
gender("Yasmin Schafer", "female").
gender("Alex Robertson", "male").
gender("Amy Hunsaker", "female").
gender("Angel Fudge", "male").
gender("Anita Fudge", "female").
gender("Augustus Robertson", "male").
gender("Brittaney Rowell", "female").
gender("Carter Fudge", "male").
gender("Dalton Fudge", "male").
gender("Daniel Rowell", "male").
gender("Danielle Banner", "female").
gender("Freeda Dent", "female").
gender("Garth Fudge", "male").
gender("Harold Banner", "male").
gender("Helga Robertson", "female").
gender("Ignacio Robertson", "male").
gender("Jack Summerlin", "male").
gender("Joelle Fudge", "female").
gender("Kristie Fudge", "female").
gender("Lyle Rowell", "male").
gender("Mavis Robertson", "female").
gender("Nancy Summerlin", "female").
gender("Nevin Dent", "male").
gender("Norris Hunsaker", "male").
gender("Rayna Fudge", "female").
gender("Robbie Hunsaker", "female").
gender("Tanya Banner", "female").

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

friend_("Ai Schafer", "Ignacio Robertson").
friend_("Alethia Kirksey", "Helga Robertson").
friend_("Alethia Kirksey", "Mavis Robertson").
friend_("Alexa Schafer", "Mavis Robertson").
friend_("Anneliese Kirkham", "Emerson Warren").
friend_("Anneliese Kirkham", "Floyd Schafer").
friend_("Anneliese Kirkham", "Amy Hunsaker").
friend_("Armando Schafer", "Maira Kirksey").
friend_("Armando Schafer", "Augustus Robertson").
friend_("Bess Kirksey", "Violet Schafer").
friend_("Bryan Kirksey", "Freeda Dent").
friend_("Bryan Kirksey", "Rayna Fudge").
friend_("Charley Kirkham", "Frederic Kirksey").
friend_("Charley Kirkham", "Oscar Warren").
friend_("Charley Kirkham", "Augustus Robertson").
friend_("Charley Kirkham", "Carter Fudge").
friend_("Charley Kirkham", "Rayna Fudge").
friend_("Emerson Warren", "Freeda Dent").
friend_("Emery Schafer", "Nancy Summerlin").
friend_("Florence Kirkham", "Rayna Fudge").
friend_("Floyd Schafer", "Joelle Fudge").
friend_("Frederic Kirksey", "Maragret Warren").
friend_("Frederic Kirksey", "Oscar Warren").
friend_("Keri Warren", "Vernon Kirkham").
friend_("Keri Warren", "Alex Robertson").
friend_("Keri Warren", "Dalton Fudge").
friend_("Keri Warren", "Nevin Dent").
friend_("Lakeshia Warren", "Alex Robertson").
friend_("Lakeshia Warren", "Danielle Banner").
friend_("Lakeshia Warren", "Robbie Hunsaker").
friend_("Maira Kirksey", "Violet Schafer").
friend_("Maira Kirksey", "Mavis Robertson").
friend_("Moises Warren", "Velia Warren").
friend_("Oscar Warren", "Nancy Summerlin").
friend_("Oscar Warren", "Tanya Banner").
friend_("Rory Kirkham", "Nevin Dent").
friend_("Rory Kirkham", "Norris Hunsaker").
friend_("Shane Kirkham", "Angel Fudge").
friend_("Shane Kirkham", "Brittaney Rowell").
friend_("Shane Kirkham", "Danielle Banner").
friend_("Shane Kirkham", "Norris Hunsaker").
friend_("Shane Kirkham", "Robbie Hunsaker").
friend_("Velia Warren", "Violet Schafer").
friend_("Velia Warren", "Lyle Rowell").
friend_("Velia Warren", "Nevin Dent").
friend_("Velia Warren", "Rayna Fudge").
friend_("Violet Schafer", "Joelle Fudge").
friend_("Violet Schafer", "Nancy Summerlin").
friend_("Yasmin Schafer", "Alex Robertson").
friend_("Yasmin Schafer", "Norris Hunsaker").
friend_("Alex Robertson", "Danielle Banner").
friend_("Alex Robertson", "Helga Robertson").
friend_("Amy Hunsaker", "Danielle Banner").
friend_("Amy Hunsaker", "Harold Banner").
friend_("Augustus Robertson", "Daniel Rowell").
friend_("Augustus Robertson", "Harold Banner").
friend_("Brittaney Rowell", "Rayna Fudge").
friend_("Carter Fudge", "Helga Robertson").
friend_("Carter Fudge", "Jack Summerlin").
friend_("Dalton Fudge", "Helga Robertson").
friend_("Dalton Fudge", "Lyle Rowell").
friend_("Dalton Fudge", "Mavis Robertson").
friend_("Daniel Rowell", "Garth Fudge").
friend_("Danielle Banner", "Garth Fudge").
friend_("Danielle Banner", "Ignacio Robertson").
friend_("Freeda Dent", "Jack Summerlin").
friend_("Freeda Dent", "Lyle Rowell").
friend_("Harold Banner", "Kristie Fudge").
friend_("Harold Banner", "Lyle Rowell").
friend_("Harold Banner", "Mavis Robertson").
friend_("Harold Banner", "Robbie Hunsaker").
friend_("Ignacio Robertson", "Jack Summerlin").
friend_("Ignacio Robertson", "Joelle Fudge").
friend_("Jack Summerlin", "Norris Hunsaker").
friend_("Joelle Fudge", "Rayna Fudge").
friend_("Nancy Summerlin", "Nevin Dent").
friend_("Nancy Summerlin", "Norris Hunsaker").
friend_("Nancy Summerlin", "Rayna Fudge").
friend_("Robbie Hunsaker", "Tanya Banner").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("industrial designer").
attribute("astronomy").
attribute("armed forces operational officer").
attribute("long-distance running").
attribute("architect").
attribute("water polo").
attribute("theatre manager").
attribute("business").
attribute("air cabin crew").
attribute("microscopy").
attribute("international aid worker").
attribute("web design").
attribute("public relations account executive").
attribute("photography").
attribute("corporate investment banker").
attribute("cycling").
attribute("early years teacher").
attribute("dancing").
attribute("presenter").
attribute("antiquing").
attribute("gaffer").
attribute("story writing").
attribute("meteorologist").
attribute("lomography").
attribute("geoscientist").
attribute("gongoozling").
attribute("leisure centre manager").
attribute("trainspotting").
attribute("recycling officer").
attribute("publishing").
attribute("corporate investment banker").
attribute("stuffed toy collecting").
attribute("agricultural engineer").
attribute("metal detecting").
attribute("technical brewer").
attribute("flower collecting and pressing").
attribute("hospital pharmacist").
attribute("marching band").
attribute("interpreter").
attribute("graffiti").
attribute("speech and language therapist").
attribute("public transport riding").
attribute("theatre manager").
attribute("whale watching").
attribute("psychotherapist").
attribute("reading").
attribute("water engineer").
attribute("medical science").
attribute("environmental health practitioner").
attribute("rock balancing").
attribute("environmental health practitioner").
attribute("surfing").
attribute("mechanical engineer").
attribute("reading").
attribute("advertising account executive").
attribute("canoeing").
attribute("chartered legal executive").
attribute("ant farming").
attribute("recruitment consultant").
attribute("photography").
attribute("geochemist").
attribute("croquet").
attribute("financial controller").
attribute("people-watching").
attribute("colour technologist").
attribute("business").
attribute("licensed conveyancer").
attribute("seashell collecting").
attribute("press sub").
attribute("skiing").
attribute("multimedia programmer").
attribute("wrestling").
attribute("recycling officer").
attribute("microscopy").
attribute("web designer").
attribute("quidditch").
attribute("occupational hygienist").
attribute("geocaching").
attribute("commissioning editor").
attribute("laser tag").
attribute("psychotherapist").
attribute("shooting sports").
attribute("chartered certified accountant").
attribute("art collecting").
attribute("associate professor").
attribute("railway studies").
attribute("government social research officer").
attribute("medical science").
attribute("research officer").
attribute("fishkeeping").
attribute("lighting technician").
attribute("hiking/backpacking").
attribute("medical illustrator").
attribute("graffiti").
attribute("prison officer").
attribute("skiing").
attribute("hydrographic surveyor").
attribute("life science").
attribute("doctor").
attribute("physics").
attribute("physiological scientist").
attribute("coin collecting").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Ai Schafer", person).
type("Alethia Kirksey", person).
type("Alexa Schafer", person).
type("Anneliese Kirkham", person).
type("Armando Schafer", person).
type("Bess Kirksey", person).
type("Bryan Kirksey", person).
type("Charley Kirkham", person).
type("Emerson Warren", person).
type("Emery Schafer", person).
type("Florence Kirkham", person).
type("Floyd Schafer", person).
type("Frederic Kirksey", person).
type("Keri Warren", person).
type("Lakeshia Warren", person).
type("Maira Kirksey", person).
type("Maragret Warren", person).
type("Moises Warren", person).
type("Oscar Warren", person).
type("Rory Kirkham", person).
type("Shane Kirkham", person).
type("Velia Warren", person).
type("Vernon Kirkham", person).
type("Violet Schafer", person).
type("Yasmin Schafer", person).
type("Alex Robertson", person).
type("Amy Hunsaker", person).
type("Angel Fudge", person).
type("Anita Fudge", person).
type("Augustus Robertson", person).
type("Brittaney Rowell", person).
type("Carter Fudge", person).
type("Dalton Fudge", person).
type("Daniel Rowell", person).
type("Danielle Banner", person).
type("Freeda Dent", person).
type("Garth Fudge", person).
type("Harold Banner", person).
type("Helga Robertson", person).
type("Ignacio Robertson", person).
type("Jack Summerlin", person).
type("Joelle Fudge", person).
type("Kristie Fudge", person).
type("Lyle Rowell", person).
type("Mavis Robertson", person).
type("Nancy Summerlin", person).
type("Nevin Dent", person).
type("Norris Hunsaker", person).
type("Rayna Fudge", person).
type("Robbie Hunsaker", person).
type("Tanya Banner", person).

:- dynamic dob/2.

dob("Ai Schafer", "0262-01-13").
dob("Alethia Kirksey", "0178-02-18").
dob("Alexa Schafer", "0285-04-14").
dob("Anneliese Kirkham", "0211-04-12").
dob("Armando Schafer", "0260-02-08").
dob("Bess Kirksey", "0233-10-06").
dob("Bryan Kirksey", "0180-08-05").
dob("Charley Kirkham", "0240-04-04").
dob("Emerson Warren", "0235-09-02").
dob("Emery Schafer", "0286-04-22").
dob("Florence Kirkham", "0239-06-25").
dob("Floyd Schafer", "0287-07-26").
dob("Frederic Kirksey", "0210-05-10").
dob("Keri Warren", "0288-08-09").
dob("Lakeshia Warren", "0323-01-25").
dob("Maira Kirksey", "0212-04-21").
dob("Maragret Warren", "0233-10-06").
dob("Moises Warren", "0291-01-08").
dob("Oscar Warren", "0262-12-04").
dob("Rory Kirkham", "0264-07-03").
dob("Shane Kirkham", "0211-10-21").
dob("Velia Warren", "0258-06-15").
dob("Vernon Kirkham", "0237-04-28").
dob("Violet Schafer", "0288-09-02").
dob("Yasmin Schafer", "0286-04-22").
dob("Alex Robertson", "0263-07-11").
dob("Amy Hunsaker", "0332-02-13").
dob("Angel Fudge", "0240-07-31").
dob("Anita Fudge", "0246-05-08").
dob("Augustus Robertson", "0295-03-10").
dob("Brittaney Rowell", "0272-10-19").
dob("Carter Fudge", "0217-01-23").
dob("Dalton Fudge", "0274-09-20").
dob("Daniel Rowell", "0300-12-30").
dob("Danielle Banner", "0304-08-31").
dob("Freeda Dent", "0240-11-01").
dob("Garth Fudge", "0243-08-05").
dob("Harold Banner", "0303-05-01").
dob("Helga Robertson", "0296-09-18").
dob("Ignacio Robertson", "0325-10-31").
dob("Jack Summerlin", "0219-06-14").
dob("Joelle Fudge", "0277-02-27").
dob("Kristie Fudge", "0217-06-20").
dob("Lyle Rowell", "0273-01-08").
dob("Mavis Robertson", "0265-10-23").
dob("Nancy Summerlin", "0220-05-26").
dob("Nevin Dent", "0238-03-23").
dob("Norris Hunsaker", "0298-10-28").
dob("Rayna Fudge", "0302-05-31").
dob("Robbie Hunsaker", "0304-05-31").
dob("Tanya Banner", "0337-03-25").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Ai Schafer", "industrial designer").
job("Alethia Kirksey", "armed forces operational officer").
job("Alexa Schafer", "architect").
job("Anneliese Kirkham", "theatre manager").
job("Armando Schafer", "air cabin crew").
job("Bess Kirksey", "international aid worker").
job("Bryan Kirksey", "public relations account executive").
job("Charley Kirkham", "corporate investment banker").
job("Emerson Warren", "early years teacher").
job("Emery Schafer", "presenter").
job("Florence Kirkham", "gaffer").
job("Floyd Schafer", "meteorologist").
job("Frederic Kirksey", "geoscientist").
job("Keri Warren", "leisure centre manager").
job("Lakeshia Warren", "recycling officer").
job("Maira Kirksey", "corporate investment banker").
job("Maragret Warren", "agricultural engineer").
job("Moises Warren", "technical brewer").
job("Oscar Warren", "hospital pharmacist").
job("Rory Kirkham", "interpreter").
job("Shane Kirkham", "speech and language therapist").
job("Velia Warren", "theatre manager").
job("Vernon Kirkham", "psychotherapist").
job("Violet Schafer", "water engineer").
job("Yasmin Schafer", "environmental health practitioner").
job("Alex Robertson", "environmental health practitioner").
job("Amy Hunsaker", "mechanical engineer").
job("Angel Fudge", "advertising account executive").
job("Anita Fudge", "chartered legal executive").
job("Augustus Robertson", "recruitment consultant").
job("Brittaney Rowell", "geochemist").
job("Carter Fudge", "financial controller").
job("Dalton Fudge", "colour technologist").
job("Daniel Rowell", "licensed conveyancer").
job("Danielle Banner", "press sub").
job("Freeda Dent", "multimedia programmer").
job("Garth Fudge", "recycling officer").
job("Harold Banner", "web designer").
job("Helga Robertson", "occupational hygienist").
job("Ignacio Robertson", "commissioning editor").
job("Jack Summerlin", "psychotherapist").
job("Joelle Fudge", "chartered certified accountant").
job("Kristie Fudge", "associate professor").
job("Lyle Rowell", "government social research officer").
job("Mavis Robertson", "research officer").
job("Nancy Summerlin", "lighting technician").
job("Nevin Dent", "medical illustrator").
job("Norris Hunsaker", "prison officer").
job("Rayna Fudge", "hydrographic surveyor").
job("Robbie Hunsaker", "doctor").
job("Tanya Banner", "physiological scientist").

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

hobby("Ai Schafer", "astronomy").
hobby("Alethia Kirksey", "long-distance running").
hobby("Alexa Schafer", "water polo").
hobby("Anneliese Kirkham", "business").
hobby("Armando Schafer", "microscopy").
hobby("Bess Kirksey", "web design").
hobby("Bryan Kirksey", "photography").
hobby("Charley Kirkham", "cycling").
hobby("Emerson Warren", "dancing").
hobby("Emery Schafer", "antiquing").
hobby("Florence Kirkham", "story writing").
hobby("Floyd Schafer", "lomography").
hobby("Frederic Kirksey", "gongoozling").
hobby("Keri Warren", "trainspotting").
hobby("Lakeshia Warren", "publishing").
hobby("Maira Kirksey", "stuffed toy collecting").
hobby("Maragret Warren", "metal detecting").
hobby("Moises Warren", "flower collecting and pressing").
hobby("Oscar Warren", "marching band").
hobby("Rory Kirkham", "graffiti").
hobby("Shane Kirkham", "public transport riding").
hobby("Velia Warren", "whale watching").
hobby("Vernon Kirkham", "reading").
hobby("Violet Schafer", "medical science").
hobby("Yasmin Schafer", "rock balancing").
hobby("Alex Robertson", "surfing").
hobby("Amy Hunsaker", "reading").
hobby("Angel Fudge", "canoeing").
hobby("Anita Fudge", "ant farming").
hobby("Augustus Robertson", "photography").
hobby("Brittaney Rowell", "croquet").
hobby("Carter Fudge", "people-watching").
hobby("Dalton Fudge", "business").
hobby("Daniel Rowell", "seashell collecting").
hobby("Danielle Banner", "skiing").
hobby("Freeda Dent", "wrestling").
hobby("Garth Fudge", "microscopy").
hobby("Harold Banner", "quidditch").
hobby("Helga Robertson", "geocaching").
hobby("Ignacio Robertson", "laser tag").
hobby("Jack Summerlin", "shooting sports").
hobby("Joelle Fudge", "art collecting").
hobby("Kristie Fudge", "railway studies").
hobby("Lyle Rowell", "medical science").
hobby("Mavis Robertson", "fishkeeping").
hobby("Nancy Summerlin", "hiking/backpacking").
hobby("Nevin Dent", "graffiti").
hobby("Norris Hunsaker", "skiing").
hobby("Rayna Fudge", "life science").
hobby("Robbie Hunsaker", "physics").
hobby("Tanya Banner", "coin collecting").

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
