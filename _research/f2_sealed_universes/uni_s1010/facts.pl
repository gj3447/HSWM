
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

parent("Alec Kruger", "Elbert Kruger").
parent("Alec Kruger", "Enedina Kruger").
parent("Aletha Bauer", "Audie Lowry").
parent("Aletha Bauer", "Kurtis Lowry").
parent("Audie Lowry", "Eugene Angle").
parent("Audie Lowry", "Rhea Angle").
parent("Cornelius Kruger", "Alec Kruger").
parent("Cornelius Kruger", "Thomasine Kruger").
parent("Demetrius Bauer", "Aletha Bauer").
parent("Demetrius Bauer", "Raul Bauer").
parent("Faith Lowry", "Robby Lowry").
parent("Faith Lowry", "Tabetha Lowry").
parent("Julian Angle", "Eugene Angle").
parent("Julian Angle", "Rhea Angle").
parent("Kurtis Lowry", "Phylis Lowry").
parent("Kurtis Lowry", "Zachery Lowry").
parent("Lawrence Lowry", "Audie Lowry").
parent("Lawrence Lowry", "Kurtis Lowry").
parent("Lela Lowry", "Robby Lowry").
parent("Lela Lowry", "Tabetha Lowry").
parent("Octavio Kruger", "Alec Kruger").
parent("Octavio Kruger", "Thomasine Kruger").
parent("Ofelia Lowry", "Audie Lowry").
parent("Ofelia Lowry", "Kurtis Lowry").
parent("Robby Lowry", "Audie Lowry").
parent("Robby Lowry", "Kurtis Lowry").
parent("Simone Kruger", "Elbert Kruger").
parent("Simone Kruger", "Enedina Kruger").
parent("Tabetha Lowry", "Cornelius Kruger").
parent("Tabetha Lowry", "Shari Kruger").
parent("Thomasine Kruger", "Stacey Sturm").
parent("Thomasine Kruger", "Sylvia Sturm").
parent("Dexter Ruiz", "Genesis Ruiz").
parent("Dexter Ruiz", "Lucas Ruiz").
parent("Genesis Ruiz", "Catalina Soper").
parent("Genesis Ruiz", "Wade Soper").
parent("Jessie Clary", "Betsy Clary").
parent("Jessie Clary", "Zachary Clary").
parent("Kurt Ruiz", "Olivia Ruiz").
parent("Kurt Ruiz", "Roderick Ruiz").
parent("Kyra Clary", "Jessie Clary").
parent("Kyra Clary", "Shae Clary").
parent("Laverne Clary", "Bernice Beard").
parent("Laverne Clary", "Mckinley Beard").
parent("Linwood Clary", "Laverne Clary").
parent("Linwood Clary", "Riley Clary").
parent("Lucas Ruiz", "Olivia Ruiz").
parent("Lucas Ruiz", "Roderick Ruiz").
parent("Mireya Clary", "Jessie Clary").
parent("Mireya Clary", "Shae Clary").
parent("Olivia Ruiz", "Laverne Clary").
parent("Olivia Ruiz", "Riley Clary").
parent("Riley Clary", "Gina Clary").
parent("Riley Clary", "Keith Clary").
parent("Romelia Ruiz", "Genesis Ruiz").
parent("Romelia Ruiz", "Lucas Ruiz").
parent("Wilbert Ruiz", "Genesis Ruiz").
parent("Wilbert Ruiz", "Lucas Ruiz").
parent("Wm Ruiz", "Demetria Ruiz").
parent("Wm Ruiz", "Dexter Ruiz").
parent("Zachary Clary", "Laverne Clary").
parent("Zachary Clary", "Riley Clary").

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

gender("Alec Kruger", "male").
gender("Aletha Bauer", "female").
gender("Audie Lowry", "female").
gender("Cornelius Kruger", "male").
gender("Demetrius Bauer", "male").
gender("Elbert Kruger", "male").
gender("Enedina Kruger", "female").
gender("Eugene Angle", "male").
gender("Faith Lowry", "female").
gender("Julian Angle", "male").
gender("Kurtis Lowry", "male").
gender("Lawrence Lowry", "male").
gender("Lela Lowry", "female").
gender("Octavio Kruger", "male").
gender("Ofelia Lowry", "female").
gender("Phylis Lowry", "female").
gender("Raul Bauer", "male").
gender("Rhea Angle", "female").
gender("Robby Lowry", "male").
gender("Shari Kruger", "female").
gender("Simone Kruger", "female").
gender("Stacey Sturm", "male").
gender("Sylvia Sturm", "female").
gender("Tabetha Lowry", "female").
gender("Thomasine Kruger", "female").
gender("Zachery Lowry", "male").
gender("Bernice Beard", "female").
gender("Betsy Clary", "female").
gender("Catalina Soper", "female").
gender("Demetria Ruiz", "female").
gender("Dexter Ruiz", "male").
gender("Genesis Ruiz", "female").
gender("Gina Clary", "female").
gender("Jessie Clary", "male").
gender("Keith Clary", "male").
gender("Kurt Ruiz", "male").
gender("Kyra Clary", "female").
gender("Laverne Clary", "female").
gender("Linwood Clary", "male").
gender("Lucas Ruiz", "male").
gender("Mckinley Beard", "male").
gender("Mireya Clary", "female").
gender("Olivia Ruiz", "female").
gender("Riley Clary", "male").
gender("Roderick Ruiz", "male").
gender("Romelia Ruiz", "female").
gender("Shae Clary", "female").
gender("Wade Soper", "male").
gender("Wilbert Ruiz", "male").
gender("Wm Ruiz", "male").
gender("Zachary Clary", "male").

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

friend_("Alec Kruger", "Linwood Clary").
friend_("Aletha Bauer", "Lawrence Lowry").
friend_("Aletha Bauer", "Rhea Angle").
friend_("Audie Lowry", "Lela Lowry").
friend_("Audie Lowry", "Phylis Lowry").
friend_("Audie Lowry", "Betsy Clary").
friend_("Audie Lowry", "Keith Clary").
friend_("Audie Lowry", "Roderick Ruiz").
friend_("Cornelius Kruger", "Enedina Kruger").
friend_("Cornelius Kruger", "Lawrence Lowry").
friend_("Cornelius Kruger", "Octavio Kruger").
friend_("Cornelius Kruger", "Tabetha Lowry").
friend_("Elbert Kruger", "Lela Lowry").
friend_("Elbert Kruger", "Mireya Clary").
friend_("Enedina Kruger", "Kurtis Lowry").
friend_("Enedina Kruger", "Roderick Ruiz").
friend_("Faith Lowry", "Robby Lowry").
friend_("Faith Lowry", "Bernice Beard").
friend_("Julian Angle", "Thomasine Kruger").
friend_("Julian Angle", "Jessie Clary").
friend_("Julian Angle", "Roderick Ruiz").
friend_("Julian Angle", "Wm Ruiz").
friend_("Kurtis Lowry", "Zachery Lowry").
friend_("Kurtis Lowry", "Linwood Clary").
friend_("Kurtis Lowry", "Wm Ruiz").
friend_("Lawrence Lowry", "Catalina Soper").
friend_("Lawrence Lowry", "Laverne Clary").
friend_("Lawrence Lowry", "Wm Ruiz").
friend_("Lela Lowry", "Ofelia Lowry").
friend_("Octavio Kruger", "Rhea Angle").
friend_("Octavio Kruger", "Riley Clary").
friend_("Phylis Lowry", "Zachary Clary").
friend_("Raul Bauer", "Romelia Ruiz").
friend_("Raul Bauer", "Wade Soper").
friend_("Robby Lowry", "Tabetha Lowry").
friend_("Robby Lowry", "Zachery Lowry").
friend_("Robby Lowry", "Romelia Ruiz").
friend_("Simone Kruger", "Zachery Lowry").
friend_("Stacey Sturm", "Tabetha Lowry").
friend_("Stacey Sturm", "Mireya Clary").
friend_("Sylvia Sturm", "Bernice Beard").
friend_("Tabetha Lowry", "Betsy Clary").
friend_("Tabetha Lowry", "Demetria Ruiz").
friend_("Tabetha Lowry", "Wilbert Ruiz").
friend_("Bernice Beard", "Betsy Clary").
friend_("Bernice Beard", "Lucas Ruiz").
friend_("Betsy Clary", "Riley Clary").
friend_("Catalina Soper", "Wm Ruiz").
friend_("Demetria Ruiz", "Olivia Ruiz").
friend_("Demetria Ruiz", "Romelia Ruiz").
friend_("Dexter Ruiz", "Linwood Clary").
friend_("Dexter Ruiz", "Wm Ruiz").
friend_("Genesis Ruiz", "Linwood Clary").
friend_("Genesis Ruiz", "Mckinley Beard").
friend_("Gina Clary", "Mckinley Beard").
friend_("Gina Clary", "Riley Clary").
friend_("Jessie Clary", "Laverne Clary").
friend_("Keith Clary", "Olivia Ruiz").
friend_("Kurt Ruiz", "Mireya Clary").
friend_("Kyra Clary", "Mireya Clary").
friend_("Kyra Clary", "Olivia Ruiz").
friend_("Linwood Clary", "Wade Soper").
friend_("Mckinley Beard", "Shae Clary").
friend_("Mireya Clary", "Shae Clary").
friend_("Romelia Ruiz", "Shae Clary").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("quarry manager").
attribute("beach volleyball").
attribute("therapist").
attribute("tennis polo").
attribute("sales executive").
attribute("engineering").
attribute("hydrographic surveyor").
attribute("wikipedia editing").
attribute("surgeon").
attribute("herping").
attribute("systems developer").
attribute("reading").
attribute("forest manager").
attribute("horseback riding").
attribute("fashion designer").
attribute("microscopy").
attribute("web designer").
attribute("auto audiophilia").
attribute("psychologist").
attribute("religious studies").
attribute("contractor").
attribute("finance").
attribute("writer").
attribute("research").
attribute("operational investment banker").
attribute("antiquities").
attribute("ecologist").
attribute("stone collecting").
attribute("clinical scientist").
attribute("science and technology studies").
attribute("best boy").
attribute("seashell collecting").
attribute("health and safety inspector").
attribute("science and technology studies").
attribute("public relations account executive").
attribute("antiquities").
attribute("armed forces operational officer").
attribute("ant farming").
attribute("quantity surveyor").
attribute("coin collecting").
attribute("merchandiser").
attribute("weightlifting").
attribute("community education officer").
attribute("web design").
attribute("ecologist").
attribute("ballet dancing").
attribute("medical secretary").
attribute("archery").
attribute("water quality scientist").
attribute("dolls").
attribute("regulatory affairs officer").
attribute("mathematics").
attribute("materials engineer").
attribute("fishkeeping").
attribute("consulting civil engineer").
attribute("ant farming").
attribute("broadcast presenter").
attribute("book collecting").
attribute("quarry manager").
attribute("inline skating").
attribute("cabin crew").
attribute("knife throwing").
attribute("psychologist").
attribute("horseshoes").
attribute("economist").
attribute("learning").
attribute("conservator").
attribute("jumping rope").
attribute("chemist").
attribute("rock balancing").
attribute("hospital doctor").
attribute("auto audiophilia").
attribute("copywriter").
attribute("bridge").
attribute("clinical molecular geneticist").
attribute("button collecting").
attribute("higher education careers adviser").
attribute("birdwatching").
attribute("administrator").
attribute("paintball").
attribute("building services engineer").
attribute("cheerleading").
attribute("recruitment consultant").
attribute("volleyball").
attribute("drilling engineer").
attribute("trainspotting").
attribute("risk analyst").
attribute("hiking/backpacking").
attribute("art gallery manager").
attribute("lacrosse").
attribute("herbalist").
attribute("roundnet").
attribute("consulting civil engineer").
attribute("research").
attribute("museum exhibitions officer").
attribute("whale watching").
attribute("corporate investment banker").
attribute("ephemera collecting").
attribute("art gallery manager").
attribute("softball").
attribute("museum exhibitions officer").
attribute("research").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Alec Kruger", person).
type("Aletha Bauer", person).
type("Audie Lowry", person).
type("Cornelius Kruger", person).
type("Demetrius Bauer", person).
type("Elbert Kruger", person).
type("Enedina Kruger", person).
type("Eugene Angle", person).
type("Faith Lowry", person).
type("Julian Angle", person).
type("Kurtis Lowry", person).
type("Lawrence Lowry", person).
type("Lela Lowry", person).
type("Octavio Kruger", person).
type("Ofelia Lowry", person).
type("Phylis Lowry", person).
type("Raul Bauer", person).
type("Rhea Angle", person).
type("Robby Lowry", person).
type("Shari Kruger", person).
type("Simone Kruger", person).
type("Stacey Sturm", person).
type("Sylvia Sturm", person).
type("Tabetha Lowry", person).
type("Thomasine Kruger", person).
type("Zachery Lowry", person).
type("Bernice Beard", person).
type("Betsy Clary", person).
type("Catalina Soper", person).
type("Demetria Ruiz", person).
type("Dexter Ruiz", person).
type("Genesis Ruiz", person).
type("Gina Clary", person).
type("Jessie Clary", person).
type("Keith Clary", person).
type("Kurt Ruiz", person).
type("Kyra Clary", person).
type("Laverne Clary", person).
type("Linwood Clary", person).
type("Lucas Ruiz", person).
type("Mckinley Beard", person).
type("Mireya Clary", person).
type("Olivia Ruiz", person).
type("Riley Clary", person).
type("Roderick Ruiz", person).
type("Romelia Ruiz", person).
type("Shae Clary", person).
type("Wade Soper", person).
type("Wilbert Ruiz", person).
type("Wm Ruiz", person).
type("Zachary Clary", person).

:- dynamic dob/2.

dob("Alec Kruger", "0215-07-04").
dob("Aletha Bauer", "0274-09-03").
dob("Audie Lowry", "0244-12-12").
dob("Cornelius Kruger", "0243-12-05").
dob("Demetrius Bauer", "0304-03-12").
dob("Elbert Kruger", "0188-06-20").
dob("Enedina Kruger", "0189-09-07").
dob("Eugene Angle", "0217-08-28").
dob("Faith Lowry", "0306-09-29").
dob("Julian Angle", "0241-11-01").
dob("Kurtis Lowry", "0245-08-20").
dob("Lawrence Lowry", "0270-12-24").
dob("Lela Lowry", "0304-09-09").
dob("Octavio Kruger", "0241-09-04").
dob("Ofelia Lowry", "0269-02-11").
dob("Phylis Lowry", "0219-02-08").
dob("Raul Bauer", "0277-10-21").
dob("Rhea Angle", "0221-08-12").
dob("Robby Lowry", "0274-12-07").
dob("Shari Kruger", "0242-03-17").
dob("Simone Kruger", "0220-11-24").
dob("Stacey Sturm", "0186-10-17").
dob("Sylvia Sturm", "0186-02-28").
dob("Tabetha Lowry", "0273-10-28").
dob("Thomasine Kruger", "0213-12-25").
dob("Zachery Lowry", "0218-09-08").
dob("Bernice Beard", "0220-07-22").
dob("Betsy Clary", "0276-07-12").
dob("Catalina Soper", "0269-11-23").
dob("Demetria Ruiz", "0326-08-20").
dob("Dexter Ruiz", "0326-03-17").
dob("Genesis Ruiz", "0294-10-15").
dob("Gina Clary", "0217-11-03").
dob("Jessie Clary", "0305-03-28").
dob("Keith Clary", "0216-12-18").
dob("Kurt Ruiz", "0298-12-04").
dob("Kyra Clary", "0328-05-19").
dob("Laverne Clary", "0249-07-24").
dob("Linwood Clary", "0274-08-29").
dob("Lucas Ruiz", "0297-04-09").
dob("Mckinley Beard", "0222-06-14").
dob("Mireya Clary", "0335-05-12").
dob("Olivia Ruiz", "0274-08-29").
dob("Riley Clary", "0251-03-18").
dob("Roderick Ruiz", "0272-08-13").
dob("Romelia Ruiz", "0325-11-18").
dob("Shae Clary", "0303-04-27").
dob("Wade Soper", "0271-09-13").
dob("Wilbert Ruiz", "0324-01-17").
dob("Wm Ruiz", "0352-07-01").
dob("Zachary Clary", "0275-09-23").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Alec Kruger", "quarry manager").
job("Aletha Bauer", "therapist").
job("Audie Lowry", "sales executive").
job("Cornelius Kruger", "hydrographic surveyor").
job("Demetrius Bauer", "surgeon").
job("Elbert Kruger", "systems developer").
job("Enedina Kruger", "forest manager").
job("Eugene Angle", "fashion designer").
job("Faith Lowry", "web designer").
job("Julian Angle", "psychologist").
job("Kurtis Lowry", "contractor").
job("Lawrence Lowry", "writer").
job("Lela Lowry", "operational investment banker").
job("Octavio Kruger", "ecologist").
job("Ofelia Lowry", "clinical scientist").
job("Phylis Lowry", "best boy").
job("Raul Bauer", "health and safety inspector").
job("Rhea Angle", "public relations account executive").
job("Robby Lowry", "armed forces operational officer").
job("Shari Kruger", "quantity surveyor").
job("Simone Kruger", "merchandiser").
job("Stacey Sturm", "community education officer").
job("Sylvia Sturm", "ecologist").
job("Tabetha Lowry", "medical secretary").
job("Thomasine Kruger", "water quality scientist").
job("Zachery Lowry", "regulatory affairs officer").
job("Bernice Beard", "materials engineer").
job("Betsy Clary", "consulting civil engineer").
job("Catalina Soper", "broadcast presenter").
job("Demetria Ruiz", "quarry manager").
job("Dexter Ruiz", "cabin crew").
job("Genesis Ruiz", "psychologist").
job("Gina Clary", "economist").
job("Jessie Clary", "conservator").
job("Keith Clary", "chemist").
job("Kurt Ruiz", "hospital doctor").
job("Kyra Clary", "copywriter").
job("Laverne Clary", "clinical molecular geneticist").
job("Linwood Clary", "higher education careers adviser").
job("Lucas Ruiz", "administrator").
job("Mckinley Beard", "building services engineer").
job("Mireya Clary", "recruitment consultant").
job("Olivia Ruiz", "drilling engineer").
job("Riley Clary", "risk analyst").
job("Roderick Ruiz", "art gallery manager").
job("Romelia Ruiz", "herbalist").
job("Shae Clary", "consulting civil engineer").
job("Wade Soper", "museum exhibitions officer").
job("Wilbert Ruiz", "corporate investment banker").
job("Wm Ruiz", "art gallery manager").
job("Zachary Clary", "museum exhibitions officer").

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

hobby("Alec Kruger", "beach volleyball").
hobby("Aletha Bauer", "tennis polo").
hobby("Audie Lowry", "engineering").
hobby("Cornelius Kruger", "wikipedia editing").
hobby("Demetrius Bauer", "herping").
hobby("Elbert Kruger", "reading").
hobby("Enedina Kruger", "horseback riding").
hobby("Eugene Angle", "microscopy").
hobby("Faith Lowry", "auto audiophilia").
hobby("Julian Angle", "religious studies").
hobby("Kurtis Lowry", "finance").
hobby("Lawrence Lowry", "research").
hobby("Lela Lowry", "antiquities").
hobby("Octavio Kruger", "stone collecting").
hobby("Ofelia Lowry", "science and technology studies").
hobby("Phylis Lowry", "seashell collecting").
hobby("Raul Bauer", "science and technology studies").
hobby("Rhea Angle", "antiquities").
hobby("Robby Lowry", "ant farming").
hobby("Shari Kruger", "coin collecting").
hobby("Simone Kruger", "weightlifting").
hobby("Stacey Sturm", "web design").
hobby("Sylvia Sturm", "ballet dancing").
hobby("Tabetha Lowry", "archery").
hobby("Thomasine Kruger", "dolls").
hobby("Zachery Lowry", "mathematics").
hobby("Bernice Beard", "fishkeeping").
hobby("Betsy Clary", "ant farming").
hobby("Catalina Soper", "book collecting").
hobby("Demetria Ruiz", "inline skating").
hobby("Dexter Ruiz", "knife throwing").
hobby("Genesis Ruiz", "horseshoes").
hobby("Gina Clary", "learning").
hobby("Jessie Clary", "jumping rope").
hobby("Keith Clary", "rock balancing").
hobby("Kurt Ruiz", "auto audiophilia").
hobby("Kyra Clary", "bridge").
hobby("Laverne Clary", "button collecting").
hobby("Linwood Clary", "birdwatching").
hobby("Lucas Ruiz", "paintball").
hobby("Mckinley Beard", "cheerleading").
hobby("Mireya Clary", "volleyball").
hobby("Olivia Ruiz", "trainspotting").
hobby("Riley Clary", "hiking/backpacking").
hobby("Roderick Ruiz", "lacrosse").
hobby("Romelia Ruiz", "roundnet").
hobby("Shae Clary", "research").
hobby("Wade Soper", "whale watching").
hobby("Wilbert Ruiz", "ephemera collecting").
hobby("Wm Ruiz", "softball").
hobby("Zachary Clary", "research").

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
