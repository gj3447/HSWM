
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

parent("Betsy Linden", "Dawn Dudley").
parent("Betsy Linden", "Mac Dudley").
parent("Brigida Stallings", "Dawn Dudley").
parent("Brigida Stallings", "Mac Dudley").
parent("Clair Caldera", "Johnna Caldera").
parent("Clair Caldera", "Woodrow Caldera").
parent("Dawn Dudley", "Johnna Caldera").
parent("Dawn Dudley", "Woodrow Caldera").
parent("Dennis Linden", "Betsy Linden").
parent("Dennis Linden", "Zackary Linden").
parent("Genny Caldera", "Bernice Caldera").
parent("Genny Caldera", "Clair Caldera").
parent("Laurette Caldera", "Bernice Caldera").
parent("Laurette Caldera", "Clair Caldera").
parent("Louella Pohl", "Sonny Pohl").
parent("Louella Pohl", "Violet Pohl").
parent("Louis Caldera", "Johnna Caldera").
parent("Louis Caldera", "Woodrow Caldera").
parent("Mac Dudley", "Maximina Dudley").
parent("Mac Dudley", "Norman Dudley").
parent("Nicky Stallings", "Monica Stallings").
parent("Nicky Stallings", "Vance Stallings").
parent("Otto Dudley", "Maximina Dudley").
parent("Otto Dudley", "Norman Dudley").
parent("Vance Stallings", "Brigida Stallings").
parent("Vance Stallings", "Porfirio Stallings").
parent("Violet Pohl", "Dawn Dudley").
parent("Violet Pohl", "Mac Dudley").
parent("Woodrow Caldera", "Felton Caldera").
parent("Woodrow Caldera", "Lashandra Caldera").
parent("Adele Corbin", "Elbert Canfield").
parent("Adele Corbin", "Lora Canfield").
parent("Clark Berman", "Luisa Berman").
parent("Clark Berman", "Willis Berman").
parent("Curt Corbin", "Adele Corbin").
parent("Curt Corbin", "Jeffery Corbin").
parent("Daryl Berman", "Luisa Berman").
parent("Daryl Berman", "Willis Berman").
parent("Katharine Whittaker", "Isaiah Whittaker").
parent("Katharine Whittaker", "Vernie Whittaker").
parent("Kraig Berman", "Clark Berman").
parent("Kraig Berman", "Rosalyn Berman").
parent("Lawrence Catalano", "Andres Catalano").
parent("Lawrence Catalano", "Nedra Catalano").
parent("Lela Whittaker", "Isaiah Whittaker").
parent("Lela Whittaker", "Vernie Whittaker").
parent("Lora Canfield", "Andres Catalano").
parent("Lora Canfield", "Nedra Catalano").
parent("Maurice Bernardo", "Jay Bernardo").
parent("Maurice Bernardo", "Nanette Bernardo").
parent("Mckinley Bernardo", "Jay Bernardo").
parent("Mckinley Bernardo", "Nanette Bernardo").
parent("Nanette Bernardo", "Lawrence Catalano").
parent("Nanette Bernardo", "Zulema Catalano").
parent("Nedra Catalano", "Luisa Berman").
parent("Nedra Catalano", "Willis Berman").
parent("Quentin Catalano", "Lawrence Catalano").
parent("Quentin Catalano", "Zulema Catalano").
parent("Vernie Whittaker", "Jay Bernardo").
parent("Vernie Whittaker", "Nanette Bernardo").
parent("Zulema Catalano", "Ben Grigg").
parent("Zulema Catalano", "Lyndsey Grigg").

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

gender("Bernice Caldera", "female").
gender("Betsy Linden", "female").
gender("Brigida Stallings", "female").
gender("Clair Caldera", "male").
gender("Dawn Dudley", "female").
gender("Dennis Linden", "male").
gender("Felton Caldera", "male").
gender("Genny Caldera", "female").
gender("Johnna Caldera", "female").
gender("Lashandra Caldera", "female").
gender("Laurette Caldera", "female").
gender("Louella Pohl", "female").
gender("Louis Caldera", "male").
gender("Mac Dudley", "male").
gender("Maximina Dudley", "female").
gender("Monica Stallings", "female").
gender("Nicky Stallings", "male").
gender("Norman Dudley", "male").
gender("Otto Dudley", "male").
gender("Porfirio Stallings", "male").
gender("Sonny Pohl", "male").
gender("Vance Stallings", "male").
gender("Violet Pohl", "female").
gender("Woodrow Caldera", "male").
gender("Zackary Linden", "male").
gender("Adele Corbin", "female").
gender("Andres Catalano", "male").
gender("Ben Grigg", "male").
gender("Clark Berman", "male").
gender("Curt Corbin", "male").
gender("Daryl Berman", "male").
gender("Elbert Canfield", "male").
gender("Isaiah Whittaker", "male").
gender("Jay Bernardo", "male").
gender("Jeffery Corbin", "male").
gender("Katharine Whittaker", "female").
gender("Kraig Berman", "male").
gender("Lawrence Catalano", "male").
gender("Lela Whittaker", "female").
gender("Lora Canfield", "female").
gender("Luisa Berman", "female").
gender("Lyndsey Grigg", "female").
gender("Maurice Bernardo", "male").
gender("Mckinley Bernardo", "male").
gender("Nanette Bernardo", "female").
gender("Nedra Catalano", "female").
gender("Quentin Catalano", "male").
gender("Rosalyn Berman", "female").
gender("Vernie Whittaker", "female").
gender("Willis Berman", "male").
gender("Zulema Catalano", "female").

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

friend_("Bernice Caldera", "Vance Stallings").
friend_("Bernice Caldera", "Mckinley Bernardo").
friend_("Brigida Stallings", "Ben Grigg").
friend_("Brigida Stallings", "Clark Berman").
friend_("Dennis Linden", "Genny Caldera").
friend_("Dennis Linden", "Nicky Stallings").
friend_("Dennis Linden", "Sonny Pohl").
friend_("Dennis Linden", "Quentin Catalano").
friend_("Felton Caldera", "Genny Caldera").
friend_("Felton Caldera", "Laurette Caldera").
friend_("Felton Caldera", "Mac Dudley").
friend_("Felton Caldera", "Nanette Bernardo").
friend_("Felton Caldera", "Nedra Catalano").
friend_("Genny Caldera", "Otto Dudley").
friend_("Genny Caldera", "Nedra Catalano").
friend_("Johnna Caldera", "Mac Dudley").
friend_("Johnna Caldera", "Jay Bernardo").
friend_("Johnna Caldera", "Rosalyn Berman").
friend_("Johnna Caldera", "Willis Berman").
friend_("Lashandra Caldera", "Elbert Canfield").
friend_("Lashandra Caldera", "Nanette Bernardo").
friend_("Lashandra Caldera", "Nedra Catalano").
friend_("Laurette Caldera", "Andres Catalano").
friend_("Laurette Caldera", "Elbert Canfield").
friend_("Louella Pohl", "Jay Bernardo").
friend_("Louella Pohl", "Jeffery Corbin").
friend_("Mac Dudley", "Katharine Whittaker").
friend_("Mac Dudley", "Lawrence Catalano").
friend_("Mac Dudley", "Willis Berman").
friend_("Maximina Dudley", "Adele Corbin").
friend_("Maximina Dudley", "Clark Berman").
friend_("Maximina Dudley", "Isaiah Whittaker").
friend_("Maximina Dudley", "Lawrence Catalano").
friend_("Monica Stallings", "Norman Dudley").
friend_("Monica Stallings", "Otto Dudley").
friend_("Monica Stallings", "Porfirio Stallings").
friend_("Monica Stallings", "Vernie Whittaker").
friend_("Nicky Stallings", "Vance Stallings").
friend_("Nicky Stallings", "Jeffery Corbin").
friend_("Nicky Stallings", "Lela Whittaker").
friend_("Nicky Stallings", "Willis Berman").
friend_("Norman Dudley", "Vance Stallings").
friend_("Norman Dudley", "Nanette Bernardo").
friend_("Norman Dudley", "Vernie Whittaker").
friend_("Otto Dudley", "Woodrow Caldera").
friend_("Otto Dudley", "Luisa Berman").
friend_("Porfirio Stallings", "Violet Pohl").
friend_("Sonny Pohl", "Lela Whittaker").
friend_("Sonny Pohl", "Willis Berman").
friend_("Violet Pohl", "Katharine Whittaker").
friend_("Violet Pohl", "Nedra Catalano").
friend_("Woodrow Caldera", "Zulema Catalano").
friend_("Zackary Linden", "Curt Corbin").
friend_("Zackary Linden", "Maurice Bernardo").
friend_("Adele Corbin", "Ben Grigg").
friend_("Adele Corbin", "Zulema Catalano").
friend_("Andres Catalano", "Lora Canfield").
friend_("Andres Catalano", "Rosalyn Berman").
friend_("Curt Corbin", "Katharine Whittaker").
friend_("Curt Corbin", "Lawrence Catalano").
friend_("Curt Corbin", "Maurice Bernardo").
friend_("Daryl Berman", "Maurice Bernardo").
friend_("Daryl Berman", "Nedra Catalano").
friend_("Elbert Canfield", "Isaiah Whittaker").
friend_("Elbert Canfield", "Jeffery Corbin").
friend_("Elbert Canfield", "Luisa Berman").
friend_("Elbert Canfield", "Nedra Catalano").
friend_("Isaiah Whittaker", "Katharine Whittaker").
friend_("Isaiah Whittaker", "Rosalyn Berman").
friend_("Jay Bernardo", "Jeffery Corbin").
friend_("Jay Bernardo", "Katharine Whittaker").
friend_("Jay Bernardo", "Kraig Berman").
friend_("Jeffery Corbin", "Willis Berman").
friend_("Kraig Berman", "Quentin Catalano").
friend_("Lawrence Catalano", "Quentin Catalano").
friend_("Lela Whittaker", "Maurice Bernardo").
friend_("Luisa Berman", "Quentin Catalano").
friend_("Lyndsey Grigg", "Zulema Catalano").
friend_("Mckinley Bernardo", "Quentin Catalano").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("community pharmacist").
attribute("podcast hosting").
attribute("sales promotion account executive").
attribute("aircraft spotting").
attribute("health visitor").
attribute("flower collecting and pressing").
attribute("patent attorney").
attribute("herping").
attribute("immigration officer").
attribute("art collecting").
attribute("location manager").
attribute("ant farming").
attribute("camera operator").
attribute("microscopy").
attribute("data processing manager").
attribute("animation").
attribute("museum curator").
attribute("cornhole").
attribute("telecommunications researcher").
attribute("business").
attribute("contractor").
attribute("canoeing").
attribute("civil service fast streamer").
attribute("meteorology").
attribute("management consultant").
attribute("reading").
attribute("government social research officer").
attribute("fishkeeping").
attribute("therapist").
attribute("myrmecology").
attribute("counselling psychologist").
attribute("darts").
attribute("customer service manager").
attribute("dancing").
attribute("clinical psychologist").
attribute("table tennis").
attribute("operations geologist").
attribute("backgammon").
attribute("advertising account planner").
attribute("disc golf").
attribute("broadcast engineer").
attribute("field hockey").
attribute("health service manager").
attribute("racquetball").
attribute("animal technologist").
attribute("skateboarding").
attribute("land surveyor").
attribute("audiophile").
attribute("leisure centre manager").
attribute("pickleball").
attribute("geneticist").
attribute("literature").
attribute("charity officer").
attribute("history").
attribute("building services engineer").
attribute("antiquities").
attribute("merchandiser").
attribute("literature").
attribute("retail banker").
attribute("meteorology").
attribute("special effects artist").
attribute("learning").
attribute("financial planner").
attribute("darts").
attribute("planning and development surveyor").
attribute("learning").
attribute("pharmacist").
attribute("ant-keeping").
attribute("heritage manager").
attribute("insect collecting").
attribute("medical physicist").
attribute("ballroom dancing").
attribute("commissioning editor").
attribute("beach volleyball").
attribute("optometrist").
attribute("finance").
attribute("theme park manager").
attribute("hobby tunneling").
attribute("civil service fast streamer").
attribute("geocaching").
attribute("customer service manager").
attribute("business").
attribute("make").
attribute("snowmobiling").
attribute("conservator").
attribute("bridge").
attribute("geophysical data processor").
attribute("jumping rope").
attribute("claims inspector").
attribute("myrmecology").
attribute("surveyor").
attribute("gongoozling").
attribute("loss adjuster").
attribute("hobby horsing").
attribute("merchandiser").
attribute("skiing").
attribute("archivist").
attribute("reading").
attribute("psychotherapist").
attribute("dominoes").
attribute("financial manager").
attribute("radio-controlled model collecting").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Bernice Caldera", person).
type("Betsy Linden", person).
type("Brigida Stallings", person).
type("Clair Caldera", person).
type("Dawn Dudley", person).
type("Dennis Linden", person).
type("Felton Caldera", person).
type("Genny Caldera", person).
type("Johnna Caldera", person).
type("Lashandra Caldera", person).
type("Laurette Caldera", person).
type("Louella Pohl", person).
type("Louis Caldera", person).
type("Mac Dudley", person).
type("Maximina Dudley", person).
type("Monica Stallings", person).
type("Nicky Stallings", person).
type("Norman Dudley", person).
type("Otto Dudley", person).
type("Porfirio Stallings", person).
type("Sonny Pohl", person).
type("Vance Stallings", person).
type("Violet Pohl", person).
type("Woodrow Caldera", person).
type("Zackary Linden", person).
type("Adele Corbin", person).
type("Andres Catalano", person).
type("Ben Grigg", person).
type("Clark Berman", person).
type("Curt Corbin", person).
type("Daryl Berman", person).
type("Elbert Canfield", person).
type("Isaiah Whittaker", person).
type("Jay Bernardo", person).
type("Jeffery Corbin", person).
type("Katharine Whittaker", person).
type("Kraig Berman", person).
type("Lawrence Catalano", person).
type("Lela Whittaker", person).
type("Lora Canfield", person).
type("Luisa Berman", person).
type("Lyndsey Grigg", person).
type("Maurice Bernardo", person).
type("Mckinley Bernardo", person).
type("Nanette Bernardo", person).
type("Nedra Catalano", person).
type("Quentin Catalano", person).
type("Rosalyn Berman", person).
type("Vernie Whittaker", person).
type("Willis Berman", person).
type("Zulema Catalano", person).

:- dynamic dob/2.

dob("Bernice Caldera", "0208-05-27").
dob("Betsy Linden", "0232-09-14").
dob("Brigida Stallings", "0236-07-04").
dob("Clair Caldera", "0208-03-07").
dob("Dawn Dudley", "0205-07-25").
dob("Dennis Linden", "0259-08-27").
dob("Felton Caldera", "0149-02-20").
dob("Genny Caldera", "0238-09-16").
dob("Johnna Caldera", "0174-10-04").
dob("Lashandra Caldera", "0147-06-17").
dob("Laurette Caldera", "0235-11-08").
dob("Louella Pohl", "0259-11-18").
dob("Louis Caldera", "0204-01-25").
dob("Mac Dudley", "0204-11-25").
dob("Maximina Dudley", "0184-12-23").
dob("Monica Stallings", "0263-08-02").
dob("Nicky Stallings", "0292-12-23").
dob("Norman Dudley", "0184-12-16").
dob("Otto Dudley", "0209-03-01").
dob("Porfirio Stallings", "0237-03-27").
dob("Sonny Pohl", "0233-08-09").
dob("Vance Stallings", "0264-12-04").
dob("Violet Pohl", "0234-04-28").
dob("Woodrow Caldera", "0177-03-01").
dob("Zackary Linden", "0233-12-07").
dob("Adele Corbin", "0236-08-27").
dob("Andres Catalano", "0179-06-26").
dob("Ben Grigg", "0184-03-12").
dob("Clark Berman", "0181-03-09").
dob("Curt Corbin", "0262-09-05").
dob("Daryl Berman", "0185-05-22").
dob("Elbert Canfield", "0207-03-08").
dob("Isaiah Whittaker", "0261-02-09").
dob("Jay Bernardo", "0236-12-24").
dob("Jeffery Corbin", "0236-08-27").
dob("Katharine Whittaker", "0294-01-28").
dob("Kraig Berman", "0204-03-31").
dob("Lawrence Catalano", "0208-04-17").
dob("Lela Whittaker", "0287-11-07").
dob("Lora Canfield", "0207-05-31").
dob("Luisa Berman", "0153-06-24").
dob("Lyndsey Grigg", "0182-04-20").
dob("Maurice Bernardo", "0264-11-03").
dob("Mckinley Bernardo", "0260-07-22").
dob("Nanette Bernardo", "0235-02-04").
dob("Nedra Catalano", "0179-09-17").
dob("Quentin Catalano", "0238-11-10").
dob("Rosalyn Berman", "0181-04-12").
dob("Vernie Whittaker", "0263-10-21").
dob("Willis Berman", "0157-09-20").
dob("Zulema Catalano", "0212-08-13").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Bernice Caldera", "community pharmacist").
job("Betsy Linden", "sales promotion account executive").
job("Brigida Stallings", "health visitor").
job("Clair Caldera", "patent attorney").
job("Dawn Dudley", "immigration officer").
job("Dennis Linden", "location manager").
job("Felton Caldera", "camera operator").
job("Genny Caldera", "data processing manager").
job("Johnna Caldera", "museum curator").
job("Lashandra Caldera", "telecommunications researcher").
job("Laurette Caldera", "contractor").
job("Louella Pohl", "civil service fast streamer").
job("Louis Caldera", "management consultant").
job("Mac Dudley", "government social research officer").
job("Maximina Dudley", "therapist").
job("Monica Stallings", "counselling psychologist").
job("Nicky Stallings", "customer service manager").
job("Norman Dudley", "clinical psychologist").
job("Otto Dudley", "operations geologist").
job("Porfirio Stallings", "advertising account planner").
job("Sonny Pohl", "broadcast engineer").
job("Vance Stallings", "health service manager").
job("Violet Pohl", "animal technologist").
job("Woodrow Caldera", "land surveyor").
job("Zackary Linden", "leisure centre manager").
job("Adele Corbin", "geneticist").
job("Andres Catalano", "charity officer").
job("Ben Grigg", "building services engineer").
job("Clark Berman", "merchandiser").
job("Curt Corbin", "retail banker").
job("Daryl Berman", "special effects artist").
job("Elbert Canfield", "financial planner").
job("Isaiah Whittaker", "planning and development surveyor").
job("Jay Bernardo", "pharmacist").
job("Jeffery Corbin", "heritage manager").
job("Katharine Whittaker", "medical physicist").
job("Kraig Berman", "commissioning editor").
job("Lawrence Catalano", "optometrist").
job("Lela Whittaker", "theme park manager").
job("Lora Canfield", "civil service fast streamer").
job("Luisa Berman", "customer service manager").
job("Lyndsey Grigg", "make").
job("Maurice Bernardo", "conservator").
job("Mckinley Bernardo", "geophysical data processor").
job("Nanette Bernardo", "claims inspector").
job("Nedra Catalano", "surveyor").
job("Quentin Catalano", "loss adjuster").
job("Rosalyn Berman", "merchandiser").
job("Vernie Whittaker", "archivist").
job("Willis Berman", "psychotherapist").
job("Zulema Catalano", "financial manager").

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

hobby("Bernice Caldera", "podcast hosting").
hobby("Betsy Linden", "aircraft spotting").
hobby("Brigida Stallings", "flower collecting and pressing").
hobby("Clair Caldera", "herping").
hobby("Dawn Dudley", "art collecting").
hobby("Dennis Linden", "ant farming").
hobby("Felton Caldera", "microscopy").
hobby("Genny Caldera", "animation").
hobby("Johnna Caldera", "cornhole").
hobby("Lashandra Caldera", "business").
hobby("Laurette Caldera", "canoeing").
hobby("Louella Pohl", "meteorology").
hobby("Louis Caldera", "reading").
hobby("Mac Dudley", "fishkeeping").
hobby("Maximina Dudley", "myrmecology").
hobby("Monica Stallings", "darts").
hobby("Nicky Stallings", "dancing").
hobby("Norman Dudley", "table tennis").
hobby("Otto Dudley", "backgammon").
hobby("Porfirio Stallings", "disc golf").
hobby("Sonny Pohl", "field hockey").
hobby("Vance Stallings", "racquetball").
hobby("Violet Pohl", "skateboarding").
hobby("Woodrow Caldera", "audiophile").
hobby("Zackary Linden", "pickleball").
hobby("Adele Corbin", "literature").
hobby("Andres Catalano", "history").
hobby("Ben Grigg", "antiquities").
hobby("Clark Berman", "literature").
hobby("Curt Corbin", "meteorology").
hobby("Daryl Berman", "learning").
hobby("Elbert Canfield", "darts").
hobby("Isaiah Whittaker", "learning").
hobby("Jay Bernardo", "ant-keeping").
hobby("Jeffery Corbin", "insect collecting").
hobby("Katharine Whittaker", "ballroom dancing").
hobby("Kraig Berman", "beach volleyball").
hobby("Lawrence Catalano", "finance").
hobby("Lela Whittaker", "hobby tunneling").
hobby("Lora Canfield", "geocaching").
hobby("Luisa Berman", "business").
hobby("Lyndsey Grigg", "snowmobiling").
hobby("Maurice Bernardo", "bridge").
hobby("Mckinley Bernardo", "jumping rope").
hobby("Nanette Bernardo", "myrmecology").
hobby("Nedra Catalano", "gongoozling").
hobby("Quentin Catalano", "hobby horsing").
hobby("Rosalyn Berman", "skiing").
hobby("Vernie Whittaker", "reading").
hobby("Willis Berman", "dominoes").
hobby("Zulema Catalano", "radio-controlled model collecting").

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
