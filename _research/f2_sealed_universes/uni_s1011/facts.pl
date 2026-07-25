
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

parent("Anjanette Marx", "Ernest Adams").
parent("Anjanette Marx", "Sona Adams").
parent("Ardath Denham", "Anjanette Marx").
parent("Ardath Denham", "Cristopher Marx").
parent("Cedrick Marx", "Anjanette Marx").
parent("Cedrick Marx", "Cristopher Marx").
parent("Conrad Marx", "Catalina Marx").
parent("Conrad Marx", "Darwin Marx").
parent("Darrell Adams", "Bee Adams").
parent("Darrell Adams", "Lyndon Adams").
parent("Darwin Marx", "Anjanette Marx").
parent("Darwin Marx", "Cristopher Marx").
parent("Elvie Adams", "Ernest Adams").
parent("Elvie Adams", "Sona Adams").
parent("Ernest Adams", "Earl Adams").
parent("Ernest Adams", "Tonya Adams").
parent("Fidel Denham", "Ardath Denham").
parent("Fidel Denham", "Silas Denham").
parent("Javier Adams", "Ernest Adams").
parent("Javier Adams", "Sona Adams").
parent("Ken Adams", "Earl Adams").
parent("Ken Adams", "Tonya Adams").
parent("Kimberlee Marx", "Catalina Marx").
parent("Kimberlee Marx", "Darwin Marx").
parent("Lyndon Adams", "Ernest Adams").
parent("Lyndon Adams", "Sona Adams").
parent("Melodie Adams", "Bee Adams").
parent("Melodie Adams", "Lyndon Adams").
parent("Monroe Adams", "Ernest Adams").
parent("Monroe Adams", "Sona Adams").
parent("Tobias Marx", "Cedrick Marx").
parent("Tobias Marx", "Suzanne Marx").
parent("Tonya Adams", "Edwina Christie").
parent("Tonya Adams", "Ivan Christie").
parent("Adalberto Burch", "Carlotta Burch").
parent("Adalberto Burch", "Stefan Burch").
parent("Adrianna Harbison", "Rashad Harbison").
parent("Adrianna Harbison", "Robyn Harbison").
parent("Chloe Burch", "German Burch").
parent("Chloe Burch", "Jesse Burch").
parent("Dwain Burch", "Carlotta Burch").
parent("Dwain Burch", "Stefan Burch").
parent("Fabian Harbison", "Rashad Harbison").
parent("Fabian Harbison", "Robyn Harbison").
parent("Georgina Burch", "Florentino Gilbreath").
parent("Georgina Burch", "Signe Gilbreath").
parent("Jarrod Burch", "German Burch").
parent("Jarrod Burch", "Jesse Burch").
parent("Jesse Burch", "Delma Phelps").
parent("Jesse Burch", "Jamel Phelps").
parent("Lea Burch", "Evelyne Burch").
parent("Lea Burch", "Mathew Burch").
parent("Mathew Burch", "Dwain Burch").
parent("Mathew Burch", "Georgina Burch").
parent("Matt Burch", "Dwain Burch").
parent("Matt Burch", "Georgina Burch").
parent("Robyn Harbison", "Carlotta Burch").
parent("Robyn Harbison", "Stefan Burch").
parent("Saul Burch", "Carlotta Burch").
parent("Saul Burch", "Stefan Burch").
parent("Signe Gilbreath", "Porfirio Chester").
parent("Signe Gilbreath", "Romona Chester").
parent("Stefan Burch", "German Burch").
parent("Stefan Burch", "Jesse Burch").
parent("Trent Burch", "Carlotta Burch").
parent("Trent Burch", "Stefan Burch").

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

gender("Anjanette Marx", "female").
gender("Ardath Denham", "female").
gender("Bee Adams", "female").
gender("Catalina Marx", "female").
gender("Cedrick Marx", "male").
gender("Conrad Marx", "male").
gender("Cristopher Marx", "male").
gender("Darrell Adams", "male").
gender("Darwin Marx", "male").
gender("Earl Adams", "male").
gender("Edwina Christie", "female").
gender("Elvie Adams", "female").
gender("Ernest Adams", "male").
gender("Fidel Denham", "male").
gender("Ivan Christie", "male").
gender("Javier Adams", "male").
gender("Ken Adams", "male").
gender("Kimberlee Marx", "female").
gender("Lyndon Adams", "male").
gender("Melodie Adams", "female").
gender("Monroe Adams", "male").
gender("Silas Denham", "male").
gender("Sona Adams", "female").
gender("Suzanne Marx", "female").
gender("Tobias Marx", "male").
gender("Tonya Adams", "female").
gender("Adalberto Burch", "male").
gender("Adrianna Harbison", "female").
gender("Carlotta Burch", "female").
gender("Chloe Burch", "female").
gender("Delma Phelps", "female").
gender("Dwain Burch", "male").
gender("Evelyne Burch", "female").
gender("Fabian Harbison", "male").
gender("Florentino Gilbreath", "male").
gender("Georgina Burch", "female").
gender("German Burch", "male").
gender("Jamel Phelps", "male").
gender("Jarrod Burch", "male").
gender("Jesse Burch", "female").
gender("Lea Burch", "female").
gender("Mathew Burch", "male").
gender("Matt Burch", "male").
gender("Porfirio Chester", "male").
gender("Rashad Harbison", "male").
gender("Robyn Harbison", "female").
gender("Romona Chester", "female").
gender("Saul Burch", "male").
gender("Signe Gilbreath", "female").
gender("Stefan Burch", "male").
gender("Trent Burch", "male").

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

friend_("Anjanette Marx", "Ivan Christie").
friend_("Anjanette Marx", "Evelyne Burch").
friend_("Ardath Denham", "Cedrick Marx").
friend_("Ardath Denham", "Darrell Adams").
friend_("Ardath Denham", "Melodie Adams").
friend_("Ardath Denham", "Tobias Marx").
friend_("Ardath Denham", "Florentino Gilbreath").
friend_("Ardath Denham", "German Burch").
friend_("Bee Adams", "Cedrick Marx").
friend_("Bee Adams", "Conrad Marx").
friend_("Bee Adams", "German Burch").
friend_("Catalina Marx", "Edwina Christie").
friend_("Catalina Marx", "Elvie Adams").
friend_("Catalina Marx", "Jamel Phelps").
friend_("Cedrick Marx", "Ernest Adams").
friend_("Cedrick Marx", "Evelyne Burch").
friend_("Cedrick Marx", "Florentino Gilbreath").
friend_("Cedrick Marx", "Mathew Burch").
friend_("Cedrick Marx", "Rashad Harbison").
friend_("Cedrick Marx", "Robyn Harbison").
friend_("Cedrick Marx", "Saul Burch").
friend_("Conrad Marx", "Lyndon Adams").
friend_("Conrad Marx", "Silas Denham").
friend_("Conrad Marx", "Suzanne Marx").
friend_("Cristopher Marx", "Ken Adams").
friend_("Cristopher Marx", "Kimberlee Marx").
friend_("Cristopher Marx", "Jarrod Burch").
friend_("Darrell Adams", "Fidel Denham").
friend_("Darrell Adams", "Florentino Gilbreath").
friend_("Darwin Marx", "Ernest Adams").
friend_("Darwin Marx", "Kimberlee Marx").
friend_("Elvie Adams", "Adrianna Harbison").
friend_("Elvie Adams", "Florentino Gilbreath").
friend_("Elvie Adams", "Robyn Harbison").
friend_("Elvie Adams", "Signe Gilbreath").
friend_("Ernest Adams", "Kimberlee Marx").
friend_("Ernest Adams", "Melodie Adams").
friend_("Ernest Adams", "German Burch").
friend_("Fidel Denham", "Javier Adams").
friend_("Fidel Denham", "Melodie Adams").
friend_("Fidel Denham", "Jamel Phelps").
friend_("Ivan Christie", "Sona Adams").
friend_("Ivan Christie", "Tobias Marx").
friend_("Ivan Christie", "Tonya Adams").
friend_("Ivan Christie", "German Burch").
friend_("Javier Adams", "Dwain Burch").
friend_("Javier Adams", "Saul Burch").
friend_("Ken Adams", "Tonya Adams").
friend_("Ken Adams", "Adrianna Harbison").
friend_("Ken Adams", "Evelyne Burch").
friend_("Ken Adams", "Fabian Harbison").
friend_("Kimberlee Marx", "Tobias Marx").
friend_("Kimberlee Marx", "Dwain Burch").
friend_("Kimberlee Marx", "Rashad Harbison").
friend_("Lyndon Adams", "German Burch").
friend_("Lyndon Adams", "Robyn Harbison").
friend_("Lyndon Adams", "Saul Burch").
friend_("Lyndon Adams", "Signe Gilbreath").
friend_("Melodie Adams", "Jamel Phelps").
friend_("Melodie Adams", "Lea Burch").
friend_("Silas Denham", "Delma Phelps").
friend_("Silas Denham", "Mathew Burch").
friend_("Silas Denham", "Saul Burch").
friend_("Suzanne Marx", "Carlotta Burch").
friend_("Suzanne Marx", "Mathew Burch").
friend_("Tobias Marx", "Delma Phelps").
friend_("Tobias Marx", "Florentino Gilbreath").
friend_("Tobias Marx", "Porfirio Chester").
friend_("Tonya Adams", "German Burch").
friend_("Tonya Adams", "Stefan Burch").
friend_("Adalberto Burch", "Dwain Burch").
friend_("Adalberto Burch", "Jamel Phelps").
friend_("Adalberto Burch", "Mathew Burch").
friend_("Adalberto Burch", "Romona Chester").
friend_("Adrianna Harbison", "Fabian Harbison").
friend_("Carlotta Burch", "Fabian Harbison").
friend_("Carlotta Burch", "German Burch").
friend_("Carlotta Burch", "Robyn Harbison").
friend_("Chloe Burch", "Florentino Gilbreath").
friend_("Delma Phelps", "Jarrod Burch").
friend_("Delma Phelps", "Mathew Burch").
friend_("Delma Phelps", "Stefan Burch").
friend_("Dwain Burch", "Fabian Harbison").
friend_("Dwain Burch", "Mathew Burch").
friend_("Dwain Burch", "Robyn Harbison").
friend_("Evelyne Burch", "Jarrod Burch").
friend_("Fabian Harbison", "Florentino Gilbreath").
friend_("Fabian Harbison", "Jamel Phelps").
friend_("Jarrod Burch", "Porfirio Chester").
friend_("Jarrod Burch", "Stefan Burch").
friend_("Jesse Burch", "Trent Burch").
friend_("Mathew Burch", "Robyn Harbison").
friend_("Porfirio Chester", "Rashad Harbison").
friend_("Robyn Harbison", "Trent Burch").
friend_("Saul Burch", "Trent Burch").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("agricultural engineer").
attribute("cheerleading").
attribute("applications developer").
attribute("philosophy").
attribute("product manager").
attribute("ant farming").
attribute("tourist information centre manager").
attribute("baseball").
attribute("statistician").
attribute("ballet dancing").
attribute("scientific laboratory technician").
attribute("learning").
attribute("embryologist").
attribute("leaves").
attribute("financial manager").
attribute("weightlifting").
attribute("conservation officer").
attribute("shortwave listening").
attribute("equities trader").
attribute("neuroscience").
attribute("outdoor activities manager").
attribute("animal fancy").
attribute("graphic designer").
attribute("rowing").
attribute("landscape architect").
attribute("longboarding").
attribute("phytotherapist").
attribute("golfing").
attribute("product designer").
attribute("aircraft spotting").
attribute("fashion designer").
attribute("stone skipping").
attribute("newspaper journalist").
attribute("fossil hunting").
attribute("actor").
attribute("cornhole").
attribute("financial manager").
attribute("gymnastics").
attribute("production designer").
attribute("picnicking").
attribute("ranger").
attribute("airsoft").
attribute("tax inspector").
attribute("sailing").
attribute("freight forwarder").
attribute("baton twirling").
attribute("trade union research officer").
attribute("psychology").
attribute("solicitor").
attribute("shooting sports").
attribute("pilot").
attribute("religious studies").
attribute("quarry manager").
attribute("australian rules football").
attribute("sales executive").
attribute("go").
attribute("commercial horticulturist").
attribute("research").
attribute("barrister").
attribute("flower collecting and pressing").
attribute("risk analyst").
attribute("insect collecting").
attribute("commercial art gallery manager").
attribute("deltiology").
attribute("agricultural consultant").
attribute("learning").
attribute("retail manager").
attribute("amateur astronomy").
attribute("product development scientist").
attribute("digital hoarding").
attribute("forensic psychologist").
attribute("gongoozling").
attribute("community education officer").
attribute("meteorology").
attribute("community arts worker").
attribute("tai chi").
attribute("field seismologist").
attribute("photography").
attribute("licensed conveyancer").
attribute("martial arts").
attribute("medical physicist").
attribute("reading").
attribute("estate manager").
attribute("philately").
attribute("historic buildings inspector").
attribute("jujitsu").
attribute("manufacturing engineer").
attribute("beekeeping").
attribute("art therapist").
attribute("action figure").
attribute("mental health nurse").
attribute("herping").
attribute("financial manager").
attribute("architecture").
attribute("sales promotion account executive").
attribute("leaves").
attribute("freight forwarder").
attribute("debate").
attribute("pathologist").
attribute("reading").
attribute("product manager").
attribute("mini golf").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Anjanette Marx", person).
type("Ardath Denham", person).
type("Bee Adams", person).
type("Catalina Marx", person).
type("Cedrick Marx", person).
type("Conrad Marx", person).
type("Cristopher Marx", person).
type("Darrell Adams", person).
type("Darwin Marx", person).
type("Earl Adams", person).
type("Edwina Christie", person).
type("Elvie Adams", person).
type("Ernest Adams", person).
type("Fidel Denham", person).
type("Ivan Christie", person).
type("Javier Adams", person).
type("Ken Adams", person).
type("Kimberlee Marx", person).
type("Lyndon Adams", person).
type("Melodie Adams", person).
type("Monroe Adams", person).
type("Silas Denham", person).
type("Sona Adams", person).
type("Suzanne Marx", person).
type("Tobias Marx", person).
type("Tonya Adams", person).
type("Adalberto Burch", person).
type("Adrianna Harbison", person).
type("Carlotta Burch", person).
type("Chloe Burch", person).
type("Delma Phelps", person).
type("Dwain Burch", person).
type("Evelyne Burch", person).
type("Fabian Harbison", person).
type("Florentino Gilbreath", person).
type("Georgina Burch", person).
type("German Burch", person).
type("Jamel Phelps", person).
type("Jarrod Burch", person).
type("Jesse Burch", person).
type("Lea Burch", person).
type("Mathew Burch", person).
type("Matt Burch", person).
type("Porfirio Chester", person).
type("Rashad Harbison", person).
type("Robyn Harbison", person).
type("Romona Chester", person).
type("Saul Burch", person).
type("Signe Gilbreath", person).
type("Stefan Burch", person).
type("Trent Burch", person).

:- dynamic dob/2.

dob("Anjanette Marx", "0254-05-01").
dob("Ardath Denham", "0280-10-31").
dob("Bee Adams", "0253-12-24").
dob("Catalina Marx", "0284-05-06").
dob("Cedrick Marx", "0282-08-05").
dob("Conrad Marx", "0307-12-11").
dob("Cristopher Marx", "0253-11-16").
dob("Darrell Adams", "0280-08-10").
dob("Darwin Marx", "0284-07-09").
dob("Earl Adams", "0198-02-09").
dob("Edwina Christie", "0171-06-06").
dob("Elvie Adams", "0252-03-22").
dob("Ernest Adams", "0223-03-04").
dob("Fidel Denham", "0310-04-08").
dob("Ivan Christie", "0171-03-22").
dob("Javier Adams", "0254-05-01").
dob("Ken Adams", "0233-06-12").
dob("Kimberlee Marx", "0314-05-19").
dob("Lyndon Adams", "0252-03-17").
dob("Melodie Adams", "0284-12-29").
dob("Monroe Adams", "0249-11-25").
dob("Silas Denham", "0277-06-27").
dob("Sona Adams", "0223-08-22").
dob("Suzanne Marx", "0281-11-05").
dob("Tobias Marx", "0302-08-09").
dob("Tonya Adams", "0200-08-08").
dob("Adalberto Burch", "0224-01-04").
dob("Adrianna Harbison", "0253-12-09").
dob("Carlotta Burch", "0193-11-08").
dob("Chloe Burch", "0194-01-14").
dob("Delma Phelps", "0142-01-09").
dob("Dwain Burch", "0216-12-19").
dob("Evelyne Burch", "0250-04-02").
dob("Fabian Harbison", "0250-09-06").
dob("Florentino Gilbreath", "0193-01-04").
dob("Georgina Burch", "0218-03-23").
dob("German Burch", "0167-07-22").
dob("Jamel Phelps", "0143-04-24").
dob("Jarrod Burch", "0195-12-31").
dob("Jesse Burch", "0168-08-25").
dob("Lea Burch", "0279-04-04").
dob("Mathew Burch", "0249-03-21").
dob("Matt Burch", "0244-03-31").
dob("Porfirio Chester", "0163-05-24").
dob("Rashad Harbison", "0221-03-17").
dob("Robyn Harbison", "0220-04-12").
dob("Romona Chester", "0163-11-04").
dob("Saul Burch", "0216-12-19").
dob("Signe Gilbreath", "0192-01-09").
dob("Stefan Burch", "0191-05-26").
dob("Trent Burch", "0221-06-09").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Anjanette Marx", "agricultural engineer").
job("Ardath Denham", "applications developer").
job("Bee Adams", "product manager").
job("Catalina Marx", "tourist information centre manager").
job("Cedrick Marx", "statistician").
job("Conrad Marx", "scientific laboratory technician").
job("Cristopher Marx", "embryologist").
job("Darrell Adams", "financial manager").
job("Darwin Marx", "conservation officer").
job("Earl Adams", "equities trader").
job("Edwina Christie", "outdoor activities manager").
job("Elvie Adams", "graphic designer").
job("Ernest Adams", "landscape architect").
job("Fidel Denham", "phytotherapist").
job("Ivan Christie", "product designer").
job("Javier Adams", "fashion designer").
job("Ken Adams", "newspaper journalist").
job("Kimberlee Marx", "actor").
job("Lyndon Adams", "financial manager").
job("Melodie Adams", "production designer").
job("Monroe Adams", "ranger").
job("Silas Denham", "tax inspector").
job("Sona Adams", "freight forwarder").
job("Suzanne Marx", "trade union research officer").
job("Tobias Marx", "solicitor").
job("Tonya Adams", "pilot").
job("Adalberto Burch", "quarry manager").
job("Adrianna Harbison", "sales executive").
job("Carlotta Burch", "commercial horticulturist").
job("Chloe Burch", "barrister").
job("Delma Phelps", "risk analyst").
job("Dwain Burch", "commercial art gallery manager").
job("Evelyne Burch", "agricultural consultant").
job("Fabian Harbison", "retail manager").
job("Florentino Gilbreath", "product development scientist").
job("Georgina Burch", "forensic psychologist").
job("German Burch", "community education officer").
job("Jamel Phelps", "community arts worker").
job("Jarrod Burch", "field seismologist").
job("Jesse Burch", "licensed conveyancer").
job("Lea Burch", "medical physicist").
job("Mathew Burch", "estate manager").
job("Matt Burch", "historic buildings inspector").
job("Porfirio Chester", "manufacturing engineer").
job("Rashad Harbison", "art therapist").
job("Robyn Harbison", "mental health nurse").
job("Romona Chester", "financial manager").
job("Saul Burch", "sales promotion account executive").
job("Signe Gilbreath", "freight forwarder").
job("Stefan Burch", "pathologist").
job("Trent Burch", "product manager").

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

hobby("Anjanette Marx", "cheerleading").
hobby("Ardath Denham", "philosophy").
hobby("Bee Adams", "ant farming").
hobby("Catalina Marx", "baseball").
hobby("Cedrick Marx", "ballet dancing").
hobby("Conrad Marx", "learning").
hobby("Cristopher Marx", "leaves").
hobby("Darrell Adams", "weightlifting").
hobby("Darwin Marx", "shortwave listening").
hobby("Earl Adams", "neuroscience").
hobby("Edwina Christie", "animal fancy").
hobby("Elvie Adams", "rowing").
hobby("Ernest Adams", "longboarding").
hobby("Fidel Denham", "golfing").
hobby("Ivan Christie", "aircraft spotting").
hobby("Javier Adams", "stone skipping").
hobby("Ken Adams", "fossil hunting").
hobby("Kimberlee Marx", "cornhole").
hobby("Lyndon Adams", "gymnastics").
hobby("Melodie Adams", "picnicking").
hobby("Monroe Adams", "airsoft").
hobby("Silas Denham", "sailing").
hobby("Sona Adams", "baton twirling").
hobby("Suzanne Marx", "psychology").
hobby("Tobias Marx", "shooting sports").
hobby("Tonya Adams", "religious studies").
hobby("Adalberto Burch", "australian rules football").
hobby("Adrianna Harbison", "go").
hobby("Carlotta Burch", "research").
hobby("Chloe Burch", "flower collecting and pressing").
hobby("Delma Phelps", "insect collecting").
hobby("Dwain Burch", "deltiology").
hobby("Evelyne Burch", "learning").
hobby("Fabian Harbison", "amateur astronomy").
hobby("Florentino Gilbreath", "digital hoarding").
hobby("Georgina Burch", "gongoozling").
hobby("German Burch", "meteorology").
hobby("Jamel Phelps", "tai chi").
hobby("Jarrod Burch", "photography").
hobby("Jesse Burch", "martial arts").
hobby("Lea Burch", "reading").
hobby("Mathew Burch", "philately").
hobby("Matt Burch", "jujitsu").
hobby("Porfirio Chester", "beekeeping").
hobby("Rashad Harbison", "action figure").
hobby("Robyn Harbison", "herping").
hobby("Romona Chester", "architecture").
hobby("Saul Burch", "leaves").
hobby("Signe Gilbreath", "debate").
hobby("Stefan Burch", "reading").
hobby("Trent Burch", "mini golf").

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
