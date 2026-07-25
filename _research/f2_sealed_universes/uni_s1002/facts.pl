
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

parent("Angela Cason", "Jann Aguayo").
parent("Angela Cason", "Lorenz Aguayo").
parent("Douglas Cason", "Ardath Cason").
parent("Douglas Cason", "Jame Cason").
parent("Estell Cason", "Bobby Hamill").
parent("Estell Cason", "Kacey Hamill").
parent("Frankie Cason", "Angela Cason").
parent("Frankie Cason", "Douglas Cason").
parent("Jewell Cason", "Nancy Cason").
parent("Jewell Cason", "Sergio Cason").
parent("Joesph Cason", "Angela Cason").
parent("Joesph Cason", "Douglas Cason").
parent("Katy Cason", "Nancy Cason").
parent("Katy Cason", "Sergio Cason").
parent("Ken Cason", "Nancy Cason").
parent("Ken Cason", "Sergio Cason").
parent("Nancy Cason", "Dante Feldman").
parent("Nancy Cason", "Manda Feldman").
parent("Page Strickland", "Angela Cason").
parent("Page Strickland", "Douglas Cason").
parent("Rick Cason", "Nancy Cason").
parent("Rick Cason", "Sergio Cason").
parent("Rochelle Strickland", "Edmond Strickland").
parent("Rochelle Strickland", "Page Strickland").
parent("Rory Cason", "Estell Cason").
parent("Rory Cason", "Ken Cason").
parent("Sergio Cason", "Angela Cason").
parent("Sergio Cason", "Douglas Cason").
parent("Teresita Cason", "Estell Cason").
parent("Teresita Cason", "Ken Cason").
parent("Tiesha Cason", "Estell Cason").
parent("Tiesha Cason", "Ken Cason").
parent("Augustus Demello", "Hulda Demello").
parent("Augustus Demello", "Pedro Demello").
parent("Bev Demello", "Hulda Demello").
parent("Bev Demello", "Pedro Demello").
parent("Cordell Tobin", "Brooks Tobin").
parent("Cordell Tobin", "Shizuko Tobin").
parent("Domingo Lemaster", "Ike Lemaster").
parent("Domingo Lemaster", "Roseanna Lemaster").
parent("Hulda Demello", "Brooks Tobin").
parent("Hulda Demello", "Shizuko Tobin").
parent("Joslyn Tobin", "Cordell Tobin").
parent("Joslyn Tobin", "Maira Tobin").
parent("Kacey Swinton", "Ike Lemaster").
parent("Kacey Swinton", "Roseanna Lemaster").
parent("Katharine Tobin", "Brooks Tobin").
parent("Katharine Tobin", "Shizuko Tobin").
parent("Leesa Breen", "Odis Breen").
parent("Leesa Breen", "Rubye Breen").
parent("Loraine Carrington", "Doyle Kasper").
parent("Loraine Carrington", "Manda Kasper").
parent("Manda Kasper", "Ike Lemaster").
parent("Manda Kasper", "Roseanna Lemaster").
parent("Marguerita Carrington", "Loraine Carrington").
parent("Marguerita Carrington", "Wilfredo Carrington").
parent("Mariann Tobin", "Cordell Tobin").
parent("Mariann Tobin", "Maira Tobin").
parent("Maximilian Swinton", "Eusebio Swinton").
parent("Maximilian Swinton", "Kacey Swinton").
parent("Rubye Breen", "Eusebio Swinton").
parent("Rubye Breen", "Kacey Swinton").
parent("Shizuko Tobin", "Loraine Carrington").
parent("Shizuko Tobin", "Wilfredo Carrington").

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

gender("Angela Cason", "female").
gender("Ardath Cason", "female").
gender("Bobby Hamill", "male").
gender("Dante Feldman", "male").
gender("Douglas Cason", "male").
gender("Edmond Strickland", "male").
gender("Estell Cason", "female").
gender("Frankie Cason", "male").
gender("Jame Cason", "male").
gender("Jann Aguayo", "female").
gender("Jewell Cason", "female").
gender("Joesph Cason", "male").
gender("Kacey Hamill", "female").
gender("Katy Cason", "female").
gender("Ken Cason", "male").
gender("Lorenz Aguayo", "male").
gender("Manda Feldman", "female").
gender("Nancy Cason", "female").
gender("Page Strickland", "female").
gender("Rick Cason", "male").
gender("Rochelle Strickland", "female").
gender("Rory Cason", "male").
gender("Sergio Cason", "male").
gender("Teresita Cason", "female").
gender("Tiesha Cason", "female").
gender("Augustus Demello", "male").
gender("Bev Demello", "female").
gender("Brooks Tobin", "male").
gender("Cordell Tobin", "male").
gender("Domingo Lemaster", "male").
gender("Doyle Kasper", "male").
gender("Eusebio Swinton", "male").
gender("Hulda Demello", "female").
gender("Ike Lemaster", "male").
gender("Joslyn Tobin", "female").
gender("Kacey Swinton", "female").
gender("Katharine Tobin", "female").
gender("Leesa Breen", "female").
gender("Loraine Carrington", "female").
gender("Maira Tobin", "female").
gender("Manda Kasper", "female").
gender("Marguerita Carrington", "female").
gender("Mariann Tobin", "female").
gender("Maximilian Swinton", "male").
gender("Odis Breen", "male").
gender("Pedro Demello", "male").
gender("Roseanna Lemaster", "female").
gender("Rubye Breen", "female").
gender("Shizuko Tobin", "female").
gender("Wilfredo Carrington", "male").

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

friend_("Angela Cason", "Jame Cason").
friend_("Angela Cason", "Joesph Cason").
friend_("Angela Cason", "Ken Cason").
friend_("Angela Cason", "Leesa Breen").
friend_("Ardath Cason", "Edmond Strickland").
friend_("Ardath Cason", "Eusebio Swinton").
friend_("Ardath Cason", "Manda Kasper").
friend_("Ardath Cason", "Odis Breen").
friend_("Bobby Hamill", "Lorenz Aguayo").
friend_("Bobby Hamill", "Rory Cason").
friend_("Bobby Hamill", "Loraine Carrington").
friend_("Bobby Hamill", "Odis Breen").
friend_("Bobby Hamill", "Roseanna Lemaster").
friend_("Dante Feldman", "Jann Aguayo").
friend_("Dante Feldman", "Page Strickland").
friend_("Dante Feldman", "Doyle Kasper").
friend_("Douglas Cason", "Frankie Cason").
friend_("Douglas Cason", "Rick Cason").
friend_("Edmond Strickland", "Estell Cason").
friend_("Edmond Strickland", "Kacey Hamill").
friend_("Edmond Strickland", "Tiesha Cason").
friend_("Estell Cason", "Nancy Cason").
friend_("Estell Cason", "Maira Tobin").
friend_("Estell Cason", "Rubye Breen").
friend_("Frankie Cason", "Katharine Tobin").
friend_("Frankie Cason", "Mariann Tobin").
friend_("Jame Cason", "Rochelle Strickland").
friend_("Jame Cason", "Hulda Demello").
friend_("Jame Cason", "Maira Tobin").
friend_("Jann Aguayo", "Katharine Tobin").
friend_("Jewell Cason", "Ken Cason").
friend_("Joesph Cason", "Ken Cason").
friend_("Joesph Cason", "Rochelle Strickland").
friend_("Kacey Hamill", "Brooks Tobin").
friend_("Katy Cason", "Manda Feldman").
friend_("Katy Cason", "Leesa Breen").
friend_("Katy Cason", "Maximilian Swinton").
friend_("Katy Cason", "Roseanna Lemaster").
friend_("Ken Cason", "Joslyn Tobin").
friend_("Lorenz Aguayo", "Maximilian Swinton").
friend_("Lorenz Aguayo", "Rubye Breen").
friend_("Lorenz Aguayo", "Shizuko Tobin").
friend_("Manda Feldman", "Domingo Lemaster").
friend_("Manda Feldman", "Roseanna Lemaster").
friend_("Manda Feldman", "Shizuko Tobin").
friend_("Nancy Cason", "Hulda Demello").
friend_("Nancy Cason", "Joslyn Tobin").
friend_("Page Strickland", "Maira Tobin").
friend_("Rick Cason", "Augustus Demello").
friend_("Rochelle Strickland", "Rory Cason").
friend_("Rochelle Strickland", "Marguerita Carrington").
friend_("Sergio Cason", "Teresita Cason").
friend_("Sergio Cason", "Eusebio Swinton").
friend_("Augustus Demello", "Bev Demello").
friend_("Bev Demello", "Brooks Tobin").
friend_("Bev Demello", "Domingo Lemaster").
friend_("Bev Demello", "Joslyn Tobin").
friend_("Bev Demello", "Shizuko Tobin").
friend_("Brooks Tobin", "Shizuko Tobin").
friend_("Cordell Tobin", "Odis Breen").
friend_("Domingo Lemaster", "Doyle Kasper").
friend_("Domingo Lemaster", "Maira Tobin").
friend_("Doyle Kasper", "Pedro Demello").
friend_("Eusebio Swinton", "Ike Lemaster").
friend_("Eusebio Swinton", "Manda Kasper").
friend_("Ike Lemaster", "Manda Kasper").
friend_("Ike Lemaster", "Odis Breen").
friend_("Ike Lemaster", "Shizuko Tobin").
friend_("Katharine Tobin", "Wilfredo Carrington").
friend_("Leesa Breen", "Manda Kasper").
friend_("Maximilian Swinton", "Wilfredo Carrington").
friend_("Odis Breen", "Wilfredo Carrington").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("licensed conveyancer").
attribute("insect collecting").
attribute("mining engineer").
attribute("people-watching").
attribute("equality and diversity officer").
attribute("scouting").
attribute("technical brewer").
attribute("leaves").
attribute("meteorologist").
attribute("bus spotting").
attribute("writer").
attribute("philosophy").
attribute("chief operating officer").
attribute("book folding").
attribute("tree surgeon").
attribute("beekeeping").
attribute("arts administrator").
attribute("herping").
attribute("commissioning editor").
attribute("hooping").
attribute("land").
attribute("shortwave listening").
attribute("chemist").
attribute("element collecting").
attribute("acupuncturist").
attribute("herbalism").
attribute("location manager").
attribute("stone collecting").
attribute("commercial horticulturist").
attribute("fishkeeping").
attribute("forest manager").
attribute("association football").
attribute("quality manager").
attribute("archaeology").
attribute("trading standards officer").
attribute("rughooking").
attribute("tour manager").
attribute("beekeeping").
attribute("IT trainer").
attribute("cornhole").
attribute("neurosurgeon").
attribute("cooking").
attribute("cartographer").
attribute("slot car").
attribute("theatre director").
attribute("cribbage").
attribute("radio broadcast assistant").
attribute("aircraft spotting").
attribute("operational investment banker").
attribute("badminton").
attribute("geographical information systems officer").
attribute("knowledge/word games").
attribute("advertising account executive").
attribute("audiophile").
attribute("buyer").
attribute("birdwatching").
attribute("automotive engineer").
attribute("beekeeping").
attribute("applications developer").
attribute("ant farming").
attribute("lexicographer").
attribute("pinball").
attribute("marketing executive").
attribute("hiking/backpacking").
attribute("archaeologist").
attribute("fishkeeping").
attribute("barrister").
attribute("fingerprint collecting").
attribute("estate agent").
attribute("laser tag").
attribute("theatre manager").
attribute("baton twirling").
attribute("osteopath").
attribute("fossil hunting").
attribute("warehouse manager").
attribute("scouting").
attribute("electrical engineer").
attribute("horseback riding").
attribute("forensic psychologist").
attribute("linguistics").
attribute("acupuncturist").
attribute("microscopy").
attribute("building services engineer").
attribute("magnet fishing").
attribute("fitness centre manager").
attribute("seashell collecting").
attribute("IT consultant").
attribute("mineral collecting").
attribute("armed forces training and education officer").
attribute("squash").
attribute("producer").
attribute("skiing").
attribute("restaurant manager").
attribute("biology").
attribute("surgeon").
attribute("geocaching").
attribute("counsellor").
attribute("deltiology").
attribute("housing manager").
attribute("audiophile").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Angela Cason", person).
type("Ardath Cason", person).
type("Bobby Hamill", person).
type("Dante Feldman", person).
type("Douglas Cason", person).
type("Edmond Strickland", person).
type("Estell Cason", person).
type("Frankie Cason", person).
type("Jame Cason", person).
type("Jann Aguayo", person).
type("Jewell Cason", person).
type("Joesph Cason", person).
type("Kacey Hamill", person).
type("Katy Cason", person).
type("Ken Cason", person).
type("Lorenz Aguayo", person).
type("Manda Feldman", person).
type("Nancy Cason", person).
type("Page Strickland", person).
type("Rick Cason", person).
type("Rochelle Strickland", person).
type("Rory Cason", person).
type("Sergio Cason", person).
type("Teresita Cason", person).
type("Tiesha Cason", person).
type("Augustus Demello", person).
type("Bev Demello", person).
type("Brooks Tobin", person).
type("Cordell Tobin", person).
type("Domingo Lemaster", person).
type("Doyle Kasper", person).
type("Eusebio Swinton", person).
type("Hulda Demello", person).
type("Ike Lemaster", person).
type("Joslyn Tobin", person).
type("Kacey Swinton", person).
type("Katharine Tobin", person).
type("Leesa Breen", person).
type("Loraine Carrington", person).
type("Maira Tobin", person).
type("Manda Kasper", person).
type("Marguerita Carrington", person).
type("Mariann Tobin", person).
type("Maximilian Swinton", person).
type("Odis Breen", person).
type("Pedro Demello", person).
type("Roseanna Lemaster", person).
type("Rubye Breen", person).
type("Shizuko Tobin", person).
type("Wilfredo Carrington", person).

:- dynamic dob/2.

dob("Angela Cason", "0264-10-14").
dob("Ardath Cason", "0233-02-25").
dob("Bobby Hamill", "0289-02-12").
dob("Dante Feldman", "0258-11-19").
dob("Douglas Cason", "0262-12-14").
dob("Edmond Strickland", "0292-07-10").
dob("Estell Cason", "0315-01-16").
dob("Frankie Cason", "0297-01-30").
dob("Jame Cason", "0233-01-04").
dob("Jann Aguayo", "0238-06-14").
dob("Jewell Cason", "0322-07-22").
dob("Joesph Cason", "0287-04-09").
dob("Kacey Hamill", "0288-09-27").
dob("Katy Cason", "0321-07-25").
dob("Ken Cason", "0317-05-15").
dob("Lorenz Aguayo", "0238-10-24").
dob("Manda Feldman", "0261-05-03").
dob("Nancy Cason", "0291-09-19").
dob("Page Strickland", "0290-11-15").
dob("Rick Cason", "0313-06-07").
dob("Rochelle Strickland", "0318-10-17").
dob("Rory Cason", "0344-12-06").
dob("Sergio Cason", "0288-10-22").
dob("Teresita Cason", "0341-12-05").
dob("Tiesha Cason", "0343-12-23").
dob("Augustus Demello", "0327-03-06").
dob("Bev Demello", "0325-08-26").
dob("Brooks Tobin", "0267-04-06").
dob("Cordell Tobin", "0299-10-21").
dob("Domingo Lemaster", "0217-12-14").
dob("Doyle Kasper", "0219-07-21").
dob("Eusebio Swinton", "0220-11-17").
dob("Hulda Demello", "0297-11-29").
dob("Ike Lemaster", "0190-04-14").
dob("Joslyn Tobin", "0321-10-10").
dob("Kacey Swinton", "0220-08-12").
dob("Katharine Tobin", "0301-03-15").
dob("Leesa Breen", "0277-07-15").
dob("Loraine Carrington", "0245-02-11").
dob("Maira Tobin", "0298-03-24").
dob("Manda Kasper", "0219-10-09").
dob("Marguerita Carrington", "0278-10-25").
dob("Mariann Tobin", "0326-04-25").
dob("Maximilian Swinton", "0240-01-15").
dob("Odis Breen", "0249-06-09").
dob("Pedro Demello", "0300-08-24").
dob("Roseanna Lemaster", "0188-02-15").
dob("Rubye Breen", "0249-01-01").
dob("Shizuko Tobin", "0271-06-27").
dob("Wilfredo Carrington", "0247-04-16").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Angela Cason", "licensed conveyancer").
job("Ardath Cason", "mining engineer").
job("Bobby Hamill", "equality and diversity officer").
job("Dante Feldman", "technical brewer").
job("Douglas Cason", "meteorologist").
job("Edmond Strickland", "writer").
job("Estell Cason", "chief operating officer").
job("Frankie Cason", "tree surgeon").
job("Jame Cason", "arts administrator").
job("Jann Aguayo", "commissioning editor").
job("Jewell Cason", "land").
job("Joesph Cason", "chemist").
job("Kacey Hamill", "acupuncturist").
job("Katy Cason", "location manager").
job("Ken Cason", "commercial horticulturist").
job("Lorenz Aguayo", "forest manager").
job("Manda Feldman", "quality manager").
job("Nancy Cason", "trading standards officer").
job("Page Strickland", "tour manager").
job("Rick Cason", "IT trainer").
job("Rochelle Strickland", "neurosurgeon").
job("Rory Cason", "cartographer").
job("Sergio Cason", "theatre director").
job("Teresita Cason", "radio broadcast assistant").
job("Tiesha Cason", "operational investment banker").
job("Augustus Demello", "geographical information systems officer").
job("Bev Demello", "advertising account executive").
job("Brooks Tobin", "buyer").
job("Cordell Tobin", "automotive engineer").
job("Domingo Lemaster", "applications developer").
job("Doyle Kasper", "lexicographer").
job("Eusebio Swinton", "marketing executive").
job("Hulda Demello", "archaeologist").
job("Ike Lemaster", "barrister").
job("Joslyn Tobin", "estate agent").
job("Kacey Swinton", "theatre manager").
job("Katharine Tobin", "osteopath").
job("Leesa Breen", "warehouse manager").
job("Loraine Carrington", "electrical engineer").
job("Maira Tobin", "forensic psychologist").
job("Manda Kasper", "acupuncturist").
job("Marguerita Carrington", "building services engineer").
job("Mariann Tobin", "fitness centre manager").
job("Maximilian Swinton", "IT consultant").
job("Odis Breen", "armed forces training and education officer").
job("Pedro Demello", "producer").
job("Roseanna Lemaster", "restaurant manager").
job("Rubye Breen", "surgeon").
job("Shizuko Tobin", "counsellor").
job("Wilfredo Carrington", "housing manager").

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

hobby("Angela Cason", "insect collecting").
hobby("Ardath Cason", "people-watching").
hobby("Bobby Hamill", "scouting").
hobby("Dante Feldman", "leaves").
hobby("Douglas Cason", "bus spotting").
hobby("Edmond Strickland", "philosophy").
hobby("Estell Cason", "book folding").
hobby("Frankie Cason", "beekeeping").
hobby("Jame Cason", "herping").
hobby("Jann Aguayo", "hooping").
hobby("Jewell Cason", "shortwave listening").
hobby("Joesph Cason", "element collecting").
hobby("Kacey Hamill", "herbalism").
hobby("Katy Cason", "stone collecting").
hobby("Ken Cason", "fishkeeping").
hobby("Lorenz Aguayo", "association football").
hobby("Manda Feldman", "archaeology").
hobby("Nancy Cason", "rughooking").
hobby("Page Strickland", "beekeeping").
hobby("Rick Cason", "cornhole").
hobby("Rochelle Strickland", "cooking").
hobby("Rory Cason", "slot car").
hobby("Sergio Cason", "cribbage").
hobby("Teresita Cason", "aircraft spotting").
hobby("Tiesha Cason", "badminton").
hobby("Augustus Demello", "knowledge/word games").
hobby("Bev Demello", "audiophile").
hobby("Brooks Tobin", "birdwatching").
hobby("Cordell Tobin", "beekeeping").
hobby("Domingo Lemaster", "ant farming").
hobby("Doyle Kasper", "pinball").
hobby("Eusebio Swinton", "hiking/backpacking").
hobby("Hulda Demello", "fishkeeping").
hobby("Ike Lemaster", "fingerprint collecting").
hobby("Joslyn Tobin", "laser tag").
hobby("Kacey Swinton", "baton twirling").
hobby("Katharine Tobin", "fossil hunting").
hobby("Leesa Breen", "scouting").
hobby("Loraine Carrington", "horseback riding").
hobby("Maira Tobin", "linguistics").
hobby("Manda Kasper", "microscopy").
hobby("Marguerita Carrington", "magnet fishing").
hobby("Mariann Tobin", "seashell collecting").
hobby("Maximilian Swinton", "mineral collecting").
hobby("Odis Breen", "squash").
hobby("Pedro Demello", "skiing").
hobby("Roseanna Lemaster", "biology").
hobby("Rubye Breen", "geocaching").
hobby("Shizuko Tobin", "deltiology").
hobby("Wilfredo Carrington", "audiophile").

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
