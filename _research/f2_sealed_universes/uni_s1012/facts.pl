
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

parent("Adam Dees", "Alvaro Dees").
parent("Adam Dees", "Cherlyn Dees").
parent("Allyson Dees", "Adam Dees").
parent("Allyson Dees", "Maximina Dees").
parent("Alvaro Dees", "Theda Dees").
parent("Alvaro Dees", "Wendell Dees").
parent("Bonnie Handley", "Adam Dees").
parent("Bonnie Handley", "Maximina Dees").
parent("Cherlyn Dees", "Rosendo Halstead").
parent("Cherlyn Dees", "Viola Halstead").
parent("Clifford Halstead", "Rosendo Halstead").
parent("Clifford Halstead", "Viola Halstead").
parent("Estella Handley", "Bonnie Handley").
parent("Estella Handley", "Riley Handley").
parent("Giovanni Dees", "Alvaro Dees").
parent("Giovanni Dees", "Cherlyn Dees").
parent("Johnetta Halstead", "Rosendo Halstead").
parent("Johnetta Halstead", "Viola Halstead").
parent("Kermit Halstead", "Rosendo Halstead").
parent("Kermit Halstead", "Viola Halstead").
parent("Monserrate Dees", "Alvaro Dees").
parent("Monserrate Dees", "Cherlyn Dees").
parent("Rhea Halstead", "Rosendo Halstead").
parent("Rhea Halstead", "Viola Halstead").
parent("Richard Dees", "Alvaro Dees").
parent("Richard Dees", "Cherlyn Dees").
parent("Rosendo Halstead", "Dustin Halstead").
parent("Rosendo Halstead", "Winnie Halstead").
parent("Viola Halstead", "Naomi Embry").
parent("Viola Halstead", "Seth Embry").
parent("Wendell Dees", "Cordell Dees").
parent("Wendell Dees", "Marcelina Dees").
parent("Alberto Lam", "Emelda Lam").
parent("Alberto Lam", "Toby Lam").
parent("Alethia Lam", "Emelda Lam").
parent("Alethia Lam", "Toby Lam").
parent("Alfred Lam", "Alan Lam").
parent("Alfred Lam", "Roxanne Lam").
parent("Aubrey Lam", "Emelda Lam").
parent("Aubrey Lam", "Toby Lam").
parent("Chelsie Reece", "Heidi Moorehead").
parent("Chelsie Reece", "Rudolf Moorehead").
parent("Cortez Michaels", "Cheree Michaels").
parent("Cortez Michaels", "Virgil Michaels").
parent("Dena Michaels", "Emelda Lam").
parent("Dena Michaels", "Toby Lam").
parent("Dorothea Quezada", "Raul Michaels").
parent("Dorothea Quezada", "Sheila Michaels").
parent("Edison Reece", "Chelsie Reece").
parent("Edison Reece", "Clifford Reece").
parent("Heidi Moorehead", "Alberto Lam").
parent("Heidi Moorehead", "Robbie Lam").
parent("Margie Moorehead", "Heidi Moorehead").
parent("Margie Moorehead", "Rudolf Moorehead").
parent("Raul Michaels", "Dena Michaels").
parent("Raul Michaels", "Rogelio Michaels").
parent("Reggie Quezada", "Dorothea Quezada").
parent("Reggie Quezada", "Jakob Quezada").
parent("Toby Lam", "Alan Lam").
parent("Toby Lam", "Roxanne Lam").
parent("Virgil Michaels", "Dena Michaels").
parent("Virgil Michaels", "Rogelio Michaels").
parent("Wilber Lam", "Emelda Lam").
parent("Wilber Lam", "Toby Lam").

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

gender("Adam Dees", "male").
gender("Allyson Dees", "female").
gender("Alvaro Dees", "male").
gender("Bonnie Handley", "female").
gender("Cherlyn Dees", "female").
gender("Clifford Halstead", "male").
gender("Cordell Dees", "male").
gender("Dustin Halstead", "male").
gender("Estella Handley", "female").
gender("Giovanni Dees", "male").
gender("Johnetta Halstead", "female").
gender("Kermit Halstead", "male").
gender("Marcelina Dees", "female").
gender("Maximina Dees", "female").
gender("Monserrate Dees", "female").
gender("Naomi Embry", "female").
gender("Rhea Halstead", "female").
gender("Richard Dees", "male").
gender("Riley Handley", "male").
gender("Rosendo Halstead", "male").
gender("Seth Embry", "male").
gender("Theda Dees", "female").
gender("Viola Halstead", "female").
gender("Wendell Dees", "male").
gender("Winnie Halstead", "female").
gender("Alan Lam", "male").
gender("Alberto Lam", "male").
gender("Alethia Lam", "female").
gender("Alfred Lam", "male").
gender("Aubrey Lam", "male").
gender("Chelsie Reece", "female").
gender("Cheree Michaels", "female").
gender("Clifford Reece", "male").
gender("Cortez Michaels", "male").
gender("Dena Michaels", "female").
gender("Dorothea Quezada", "female").
gender("Edison Reece", "male").
gender("Emelda Lam", "female").
gender("Heidi Moorehead", "female").
gender("Jakob Quezada", "male").
gender("Margie Moorehead", "female").
gender("Raul Michaels", "male").
gender("Reggie Quezada", "male").
gender("Robbie Lam", "female").
gender("Rogelio Michaels", "male").
gender("Roxanne Lam", "female").
gender("Rudolf Moorehead", "male").
gender("Sheila Michaels", "female").
gender("Toby Lam", "male").
gender("Virgil Michaels", "male").
gender("Wilber Lam", "male").

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

friend_("Adam Dees", "Cherlyn Dees").
friend_("Adam Dees", "Viola Halstead").
friend_("Adam Dees", "Wendell Dees").
friend_("Adam Dees", "Roxanne Lam").
friend_("Allyson Dees", "Alethia Lam").
friend_("Allyson Dees", "Alfred Lam").
friend_("Allyson Dees", "Rudolf Moorehead").
friend_("Alvaro Dees", "Marcelina Dees").
friend_("Alvaro Dees", "Maximina Dees").
friend_("Alvaro Dees", "Reggie Quezada").
friend_("Bonnie Handley", "Cherlyn Dees").
friend_("Bonnie Handley", "Clifford Halstead").
friend_("Bonnie Handley", "Dena Michaels").
friend_("Bonnie Handley", "Sheila Michaels").
friend_("Cherlyn Dees", "Clifford Halstead").
friend_("Cherlyn Dees", "Cordell Dees").
friend_("Cherlyn Dees", "Sheila Michaels").
friend_("Clifford Halstead", "Marcelina Dees").
friend_("Clifford Halstead", "Alan Lam").
friend_("Cordell Dees", "Johnetta Halstead").
friend_("Cordell Dees", "Richard Dees").
friend_("Cordell Dees", "Alethia Lam").
friend_("Cordell Dees", "Emelda Lam").
friend_("Estella Handley", "Rosendo Halstead").
friend_("Estella Handley", "Dorothea Quezada").
friend_("Giovanni Dees", "Kermit Halstead").
friend_("Giovanni Dees", "Raul Michaels").
friend_("Kermit Halstead", "Maximina Dees").
friend_("Kermit Halstead", "Rhea Halstead").
friend_("Kermit Halstead", "Viola Halstead").
friend_("Kermit Halstead", "Margie Moorehead").
friend_("Maximina Dees", "Edison Reece").
friend_("Monserrate Dees", "Alberto Lam").
friend_("Monserrate Dees", "Emelda Lam").
friend_("Monserrate Dees", "Rogelio Michaels").
friend_("Rhea Halstead", "Wendell Dees").
friend_("Richard Dees", "Cheree Michaels").
friend_("Richard Dees", "Clifford Reece").
friend_("Richard Dees", "Wilber Lam").
friend_("Riley Handley", "Emelda Lam").
friend_("Riley Handley", "Reggie Quezada").
friend_("Riley Handley", "Toby Lam").
friend_("Rosendo Halstead", "Viola Halstead").
friend_("Rosendo Halstead", "Alan Lam").
friend_("Theda Dees", "Rogelio Michaels").
friend_("Viola Halstead", "Alan Lam").
friend_("Wendell Dees", "Toby Lam").
friend_("Winnie Halstead", "Robbie Lam").
friend_("Alan Lam", "Edison Reece").
friend_("Alan Lam", "Sheila Michaels").
friend_("Alberto Lam", "Heidi Moorehead").
friend_("Alberto Lam", "Jakob Quezada").
friend_("Alberto Lam", "Roxanne Lam").
friend_("Alberto Lam", "Virgil Michaels").
friend_("Alethia Lam", "Virgil Michaels").
friend_("Alfred Lam", "Rudolf Moorehead").
friend_("Chelsie Reece", "Edison Reece").
friend_("Chelsie Reece", "Wilber Lam").
friend_("Cheree Michaels", "Reggie Quezada").
friend_("Cortez Michaels", "Rogelio Michaels").
friend_("Emelda Lam", "Margie Moorehead").
friend_("Heidi Moorehead", "Robbie Lam").
friend_("Reggie Quezada", "Rogelio Michaels").
friend_("Robbie Lam", "Roxanne Lam").
friend_("Robbie Lam", "Toby Lam").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("facilities manager").
attribute("fitness").
attribute("passenger transport manager").
attribute("sports memorabilia").
attribute("chief marketing officer").
attribute("crystals").
attribute("barista").
attribute("research").
attribute("geochemist").
attribute("martial arts").
attribute("medical technical officer").
attribute("butterfly watching").
attribute("advice worker").
attribute("microscopy").
attribute("geoscientist").
attribute("canoeing").
attribute("event organiser").
attribute("roller derby").
attribute("lecturer").
attribute("model united nations").
attribute("academic librarian").
attribute("reading").
attribute("electronics engineer").
attribute("ant farming").
attribute("magazine journalist").
attribute("fishkeeping").
attribute("cabin crew").
attribute("radio-controlled model collecting").
attribute("professor emeritus").
attribute("transit map collecting").
attribute("health service manager").
attribute("longboarding").
attribute("lexicographer").
attribute("color guard").
attribute("consulting civil engineer").
attribute("bus spotting").
attribute("counsellor").
attribute("auto audiophilia").
attribute("veterinary surgeon").
attribute("mini golf").
attribute("horticultural consultant").
attribute("butterfly watching").
attribute("glass blower").
attribute("microscopy").
attribute("warden").
attribute("mountain biking").
attribute("magazine features editor").
attribute("fossil hunting").
attribute("horticultural consultant").
attribute("stamp collecting").
attribute("holiday representative").
attribute("fishkeeping").
attribute("warehouse manager").
attribute("insect collecting").
attribute("arboriculturist").
attribute("stone collecting").
attribute("conference centre manager").
attribute("cricket").
attribute("professor emeritus").
attribute("rowing").
attribute("broadcast engineer").
attribute("sled dog racing").
attribute("patent examiner").
attribute("taekwondo").
attribute("heritage manager").
attribute("leaves").
attribute("youth worker").
attribute("meditation").
attribute("academic librarian").
attribute("science and technology studies").
attribute("commissioning editor").
attribute("research").
attribute("materials engineer").
attribute("animation").
attribute("environmental consultant").
attribute("baseball").
attribute("lighting technician").
attribute("mineral collecting").
attribute("psychiatrist").
attribute("unicycling").
attribute("adult nurse").
attribute("cooking").
attribute("investment banker").
attribute("public transport riding").
attribute("training and development officer").
attribute("cricket").
attribute("publishing rights manager").
attribute("meditation").
attribute("politician's assistant").
attribute("fingerprint collecting").
attribute("health and safety inspector").
attribute("fishkeeping").
attribute("landscape architect").
attribute("speedcubing").
attribute("transport planner").
attribute("blacksmithing").
attribute("hospital pharmacist").
attribute("sports memorabilia").
attribute("editor").
attribute("antiquing").
attribute("special educational needs teacher").
attribute("coin collecting").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Adam Dees", person).
type("Allyson Dees", person).
type("Alvaro Dees", person).
type("Bonnie Handley", person).
type("Cherlyn Dees", person).
type("Clifford Halstead", person).
type("Cordell Dees", person).
type("Dustin Halstead", person).
type("Estella Handley", person).
type("Giovanni Dees", person).
type("Johnetta Halstead", person).
type("Kermit Halstead", person).
type("Marcelina Dees", person).
type("Maximina Dees", person).
type("Monserrate Dees", person).
type("Naomi Embry", person).
type("Rhea Halstead", person).
type("Richard Dees", person).
type("Riley Handley", person).
type("Rosendo Halstead", person).
type("Seth Embry", person).
type("Theda Dees", person).
type("Viola Halstead", person).
type("Wendell Dees", person).
type("Winnie Halstead", person).
type("Alan Lam", person).
type("Alberto Lam", person).
type("Alethia Lam", person).
type("Alfred Lam", person).
type("Aubrey Lam", person).
type("Chelsie Reece", person).
type("Cheree Michaels", person).
type("Clifford Reece", person).
type("Cortez Michaels", person).
type("Dena Michaels", person).
type("Dorothea Quezada", person).
type("Edison Reece", person).
type("Emelda Lam", person).
type("Heidi Moorehead", person).
type("Jakob Quezada", person).
type("Margie Moorehead", person).
type("Raul Michaels", person).
type("Reggie Quezada", person).
type("Robbie Lam", person).
type("Rogelio Michaels", person).
type("Roxanne Lam", person).
type("Rudolf Moorehead", person).
type("Sheila Michaels", person).
type("Toby Lam", person).
type("Virgil Michaels", person).
type("Wilber Lam", person).

:- dynamic dob/2.

dob("Adam Dees", "0277-04-25").
dob("Allyson Dees", "0305-01-21").
dob("Alvaro Dees", "0252-03-05").
dob("Bonnie Handley", "0300-01-30").
dob("Cherlyn Dees", "0253-04-21").
dob("Clifford Halstead", "0252-04-05").
dob("Cordell Dees", "0202-08-06").
dob("Dustin Halstead", "0195-03-01").
dob("Estella Handley", "0329-10-10").
dob("Giovanni Dees", "0279-12-27").
dob("Johnetta Halstead", "0255-08-03").
dob("Kermit Halstead", "0254-06-12").
dob("Marcelina Dees", "0201-12-23").
dob("Maximina Dees", "0276-03-07").
dob("Monserrate Dees", "0279-02-18").
dob("Naomi Embry", "0196-11-04").
dob("Rhea Halstead", "0248-07-27").
dob("Richard Dees", "0278-08-31").
dob("Riley Handley", "0302-09-10").
dob("Rosendo Halstead", "0226-06-25").
dob("Seth Embry", "0195-09-13").
dob("Theda Dees", "0228-09-17").
dob("Viola Halstead", "0226-04-08").
dob("Wendell Dees", "0228-10-08").
dob("Winnie Halstead", "0194-04-23").
dob("Alan Lam", "0170-09-09").
dob("Alberto Lam", "0234-04-21").
dob("Alethia Lam", "0228-04-18").
dob("Alfred Lam", "0193-10-16").
dob("Aubrey Lam", "0226-11-20").
dob("Chelsie Reece", "0292-02-20").
dob("Cheree Michaels", "0257-12-26").
dob("Clifford Reece", "0292-01-26").
dob("Cortez Michaels", "0285-02-08").
dob("Dena Michaels", "0225-01-04").
dob("Dorothea Quezada", "0277-12-22").
dob("Edison Reece", "0318-07-26").
dob("Emelda Lam", "0197-05-12").
dob("Heidi Moorehead", "0258-12-16").
dob("Jakob Quezada", "0273-09-11").
dob("Margie Moorehead", "0286-04-22").
dob("Raul Michaels", "0248-05-13").
dob("Reggie Quezada", "0304-02-06").
dob("Robbie Lam", "0233-06-01").
dob("Rogelio Michaels", "0224-04-02").
dob("Roxanne Lam", "0166-01-01").
dob("Rudolf Moorehead", "0261-09-10").
dob("Sheila Michaels", "0250-04-24").
dob("Toby Lam", "0200-09-18").
dob("Virgil Michaels", "0255-01-03").
dob("Wilber Lam", "0229-11-07").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Adam Dees", "facilities manager").
job("Allyson Dees", "passenger transport manager").
job("Alvaro Dees", "chief marketing officer").
job("Bonnie Handley", "barista").
job("Cherlyn Dees", "geochemist").
job("Clifford Halstead", "medical technical officer").
job("Cordell Dees", "advice worker").
job("Dustin Halstead", "geoscientist").
job("Estella Handley", "event organiser").
job("Giovanni Dees", "lecturer").
job("Johnetta Halstead", "academic librarian").
job("Kermit Halstead", "electronics engineer").
job("Marcelina Dees", "magazine journalist").
job("Maximina Dees", "cabin crew").
job("Monserrate Dees", "professor emeritus").
job("Naomi Embry", "health service manager").
job("Rhea Halstead", "lexicographer").
job("Richard Dees", "consulting civil engineer").
job("Riley Handley", "counsellor").
job("Rosendo Halstead", "veterinary surgeon").
job("Seth Embry", "horticultural consultant").
job("Theda Dees", "glass blower").
job("Viola Halstead", "warden").
job("Wendell Dees", "magazine features editor").
job("Winnie Halstead", "horticultural consultant").
job("Alan Lam", "holiday representative").
job("Alberto Lam", "warehouse manager").
job("Alethia Lam", "arboriculturist").
job("Alfred Lam", "conference centre manager").
job("Aubrey Lam", "professor emeritus").
job("Chelsie Reece", "broadcast engineer").
job("Cheree Michaels", "patent examiner").
job("Clifford Reece", "heritage manager").
job("Cortez Michaels", "youth worker").
job("Dena Michaels", "academic librarian").
job("Dorothea Quezada", "commissioning editor").
job("Edison Reece", "materials engineer").
job("Emelda Lam", "environmental consultant").
job("Heidi Moorehead", "lighting technician").
job("Jakob Quezada", "psychiatrist").
job("Margie Moorehead", "adult nurse").
job("Raul Michaels", "investment banker").
job("Reggie Quezada", "training and development officer").
job("Robbie Lam", "publishing rights manager").
job("Rogelio Michaels", "politician's assistant").
job("Roxanne Lam", "health and safety inspector").
job("Rudolf Moorehead", "landscape architect").
job("Sheila Michaels", "transport planner").
job("Toby Lam", "hospital pharmacist").
job("Virgil Michaels", "editor").
job("Wilber Lam", "special educational needs teacher").

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

hobby("Adam Dees", "fitness").
hobby("Allyson Dees", "sports memorabilia").
hobby("Alvaro Dees", "crystals").
hobby("Bonnie Handley", "research").
hobby("Cherlyn Dees", "martial arts").
hobby("Clifford Halstead", "butterfly watching").
hobby("Cordell Dees", "microscopy").
hobby("Dustin Halstead", "canoeing").
hobby("Estella Handley", "roller derby").
hobby("Giovanni Dees", "model united nations").
hobby("Johnetta Halstead", "reading").
hobby("Kermit Halstead", "ant farming").
hobby("Marcelina Dees", "fishkeeping").
hobby("Maximina Dees", "radio-controlled model collecting").
hobby("Monserrate Dees", "transit map collecting").
hobby("Naomi Embry", "longboarding").
hobby("Rhea Halstead", "color guard").
hobby("Richard Dees", "bus spotting").
hobby("Riley Handley", "auto audiophilia").
hobby("Rosendo Halstead", "mini golf").
hobby("Seth Embry", "butterfly watching").
hobby("Theda Dees", "microscopy").
hobby("Viola Halstead", "mountain biking").
hobby("Wendell Dees", "fossil hunting").
hobby("Winnie Halstead", "stamp collecting").
hobby("Alan Lam", "fishkeeping").
hobby("Alberto Lam", "insect collecting").
hobby("Alethia Lam", "stone collecting").
hobby("Alfred Lam", "cricket").
hobby("Aubrey Lam", "rowing").
hobby("Chelsie Reece", "sled dog racing").
hobby("Cheree Michaels", "taekwondo").
hobby("Clifford Reece", "leaves").
hobby("Cortez Michaels", "meditation").
hobby("Dena Michaels", "science and technology studies").
hobby("Dorothea Quezada", "research").
hobby("Edison Reece", "animation").
hobby("Emelda Lam", "baseball").
hobby("Heidi Moorehead", "mineral collecting").
hobby("Jakob Quezada", "unicycling").
hobby("Margie Moorehead", "cooking").
hobby("Raul Michaels", "public transport riding").
hobby("Reggie Quezada", "cricket").
hobby("Robbie Lam", "meditation").
hobby("Rogelio Michaels", "fingerprint collecting").
hobby("Roxanne Lam", "fishkeeping").
hobby("Rudolf Moorehead", "speedcubing").
hobby("Sheila Michaels", "blacksmithing").
hobby("Toby Lam", "sports memorabilia").
hobby("Virgil Michaels", "antiquing").
hobby("Wilber Lam", "coin collecting").

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
