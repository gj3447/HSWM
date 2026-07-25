
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

parent("Allie Curiel", "Allyson Veliz").
parent("Allie Curiel", "Bernie Veliz").
parent("Angel Curiel", "Kisha Curiel").
parent("Angel Curiel", "Michael Curiel").
parent("Benny Curiel", "Abdul Curiel").
parent("Benny Curiel", "Ming Curiel").
parent("Elvie Nagel", "Abdul Curiel").
parent("Elvie Nagel", "Ming Curiel").
parent("Jeffery Curiel", "Leigh Curiel").
parent("Jeffery Curiel", "Ron Curiel").
parent("Kacey Nagel", "Carrol Nagel").
parent("Kacey Nagel", "Elvie Nagel").
parent("Kennith Curiel", "Abdul Curiel").
parent("Kennith Curiel", "Ming Curiel").
parent("Leigh Curiel", "Florian Irving").
parent("Leigh Curiel", "Manuela Irving").
parent("Lucile Curiel", "Gabriele Curiel").
parent("Lucile Curiel", "Kennith Curiel").
parent("Michael Curiel", "Gabriele Curiel").
parent("Michael Curiel", "Kennith Curiel").
parent("Ming Curiel", "Antwan Garcia").
parent("Ming Curiel", "Miki Garcia").
parent("Murray Nagel", "Carrol Nagel").
parent("Murray Nagel", "Elvie Nagel").
parent("Nick Curiel", "Leigh Curiel").
parent("Nick Curiel", "Ron Curiel").
parent("Ron Curiel", "Abdul Curiel").
parent("Ron Curiel", "Ming Curiel").
parent("Sharolyn Curiel", "Allie Curiel").
parent("Sharolyn Curiel", "Benny Curiel").
parent("Tabetha Curiel", "Abdul Curiel").
parent("Tabetha Curiel", "Ming Curiel").
parent("Adele Butcher", "Hank Nagle").
parent("Adele Butcher", "Maude Nagle").
parent("Anibal Camacho", "Ismael Camacho").
parent("Anibal Camacho", "Zana Camacho").
parent("Blair Gainey", "Adele Butcher").
parent("Blair Gainey", "Clayton Butcher").
parent("Clayton Butcher", "Brett Butcher").
parent("Clayton Butcher", "Jacqueline Butcher").
parent("Delores Reinke", "Julian Reinke").
parent("Delores Reinke", "Naomi Reinke").
parent("Isabella Brockway", "Loretta Gainey").
parent("Isabella Brockway", "Owen Gainey").
parent("Ismael Camacho", "Francesca Camacho").
parent("Ismael Camacho", "Frederick Camacho").
parent("Johnna Beason", "Loretta Gainey").
parent("Johnna Beason", "Owen Gainey").
parent("Joshua Gainey", "Blair Gainey").
parent("Joshua Gainey", "Pete Gainey").
parent("Maude Nagle", "Julian Reinke").
parent("Maude Nagle", "Naomi Reinke").
parent("Megan Beason", "Johnna Beason").
parent("Megan Beason", "Jules Beason").
parent("Pete Gainey", "Loretta Gainey").
parent("Pete Gainey", "Owen Gainey").
parent("Tena Brockway", "Donovan Brockway").
parent("Tena Brockway", "Isabella Brockway").
parent("Zana Camacho", "Blair Gainey").
parent("Zana Camacho", "Pete Gainey").

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

gender("Abdul Curiel", "male").
gender("Allie Curiel", "female").
gender("Allyson Veliz", "female").
gender("Angel Curiel", "male").
gender("Antwan Garcia", "male").
gender("Benny Curiel", "male").
gender("Bernie Veliz", "male").
gender("Carrol Nagel", "male").
gender("Elvie Nagel", "female").
gender("Florian Irving", "male").
gender("Gabriele Curiel", "female").
gender("Jeffery Curiel", "male").
gender("Kacey Nagel", "female").
gender("Kennith Curiel", "male").
gender("Kisha Curiel", "female").
gender("Leigh Curiel", "female").
gender("Lucile Curiel", "female").
gender("Manuela Irving", "female").
gender("Michael Curiel", "male").
gender("Miki Garcia", "female").
gender("Ming Curiel", "female").
gender("Murray Nagel", "male").
gender("Nick Curiel", "male").
gender("Ron Curiel", "male").
gender("Sharolyn Curiel", "female").
gender("Tabetha Curiel", "female").
gender("Adele Butcher", "female").
gender("Anibal Camacho", "male").
gender("Blair Gainey", "female").
gender("Brett Butcher", "male").
gender("Clayton Butcher", "male").
gender("Delores Reinke", "female").
gender("Donovan Brockway", "male").
gender("Francesca Camacho", "female").
gender("Frederick Camacho", "male").
gender("Hank Nagle", "male").
gender("Isabella Brockway", "female").
gender("Ismael Camacho", "male").
gender("Jacqueline Butcher", "female").
gender("Johnna Beason", "female").
gender("Joshua Gainey", "male").
gender("Jules Beason", "male").
gender("Julian Reinke", "male").
gender("Loretta Gainey", "female").
gender("Maude Nagle", "female").
gender("Megan Beason", "female").
gender("Naomi Reinke", "female").
gender("Owen Gainey", "male").
gender("Pete Gainey", "male").
gender("Tena Brockway", "female").
gender("Zana Camacho", "female").

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

friend_("Abdul Curiel", "Nick Curiel").
friend_("Abdul Curiel", "Joshua Gainey").
friend_("Abdul Curiel", "Jules Beason").
friend_("Abdul Curiel", "Naomi Reinke").
friend_("Allie Curiel", "Michael Curiel").
friend_("Allie Curiel", "Ron Curiel").
friend_("Allie Curiel", "Jacqueline Butcher").
friend_("Allie Curiel", "Johnna Beason").
friend_("Allie Curiel", "Tena Brockway").
friend_("Allyson Veliz", "Florian Irving").
friend_("Allyson Veliz", "Nick Curiel").
friend_("Allyson Veliz", "Hank Nagle").
friend_("Allyson Veliz", "Isabella Brockway").
friend_("Angel Curiel", "Ismael Camacho").
friend_("Angel Curiel", "Zana Camacho").
friend_("Antwan Garcia", "Kennith Curiel").
friend_("Antwan Garcia", "Murray Nagel").
friend_("Antwan Garcia", "Clayton Butcher").
friend_("Antwan Garcia", "Julian Reinke").
friend_("Antwan Garcia", "Maude Nagle").
friend_("Benny Curiel", "Donovan Brockway").
friend_("Benny Curiel", "Francesca Camacho").
friend_("Benny Curiel", "Zana Camacho").
friend_("Carrol Nagel", "Jeffery Curiel").
friend_("Carrol Nagel", "Ron Curiel").
friend_("Carrol Nagel", "Sharolyn Curiel").
friend_("Carrol Nagel", "Francesca Camacho").
friend_("Carrol Nagel", "Johnna Beason").
friend_("Carrol Nagel", "Pete Gainey").
friend_("Elvie Nagel", "Isabella Brockway").
friend_("Elvie Nagel", "Jacqueline Butcher").
friend_("Elvie Nagel", "Megan Beason").
friend_("Florian Irving", "Owen Gainey").
friend_("Gabriele Curiel", "Sharolyn Curiel").
friend_("Gabriele Curiel", "Brett Butcher").
friend_("Gabriele Curiel", "Johnna Beason").
friend_("Jeffery Curiel", "Julian Reinke").
friend_("Jeffery Curiel", "Zana Camacho").
friend_("Kacey Nagel", "Nick Curiel").
friend_("Kacey Nagel", "Maude Nagle").
friend_("Kacey Nagel", "Pete Gainey").
friend_("Kennith Curiel", "Kisha Curiel").
friend_("Kennith Curiel", "Ming Curiel").
friend_("Kennith Curiel", "Adele Butcher").
friend_("Kennith Curiel", "Clayton Butcher").
friend_("Kennith Curiel", "Frederick Camacho").
friend_("Kennith Curiel", "Loretta Gainey").
friend_("Kisha Curiel", "Lucile Curiel").
friend_("Kisha Curiel", "Ming Curiel").
friend_("Kisha Curiel", "Brett Butcher").
friend_("Kisha Curiel", "Jacqueline Butcher").
friend_("Kisha Curiel", "Joshua Gainey").
friend_("Leigh Curiel", "Michael Curiel").
friend_("Leigh Curiel", "Ismael Camacho").
friend_("Leigh Curiel", "Johnna Beason").
friend_("Lucile Curiel", "Michael Curiel").
friend_("Lucile Curiel", "Blair Gainey").
friend_("Lucile Curiel", "Donovan Brockway").
friend_("Michael Curiel", "Tena Brockway").
friend_("Miki Garcia", "Ming Curiel").
friend_("Miki Garcia", "Nick Curiel").
friend_("Miki Garcia", "Loretta Gainey").
friend_("Ming Curiel", "Adele Butcher").
friend_("Ming Curiel", "Frederick Camacho").
friend_("Nick Curiel", "Clayton Butcher").
friend_("Nick Curiel", "Pete Gainey").
friend_("Ron Curiel", "Loretta Gainey").
friend_("Sharolyn Curiel", "Joshua Gainey").
friend_("Tabetha Curiel", "Ismael Camacho").
friend_("Tabetha Curiel", "Pete Gainey").
friend_("Adele Butcher", "Jacqueline Butcher").
friend_("Anibal Camacho", "Francesca Camacho").
friend_("Anibal Camacho", "Isabella Brockway").
friend_("Delores Reinke", "Maude Nagle").
friend_("Frederick Camacho", "Joshua Gainey").
friend_("Frederick Camacho", "Tena Brockway").
friend_("Hank Nagle", "Tena Brockway").
friend_("Isabella Brockway", "Joshua Gainey").
friend_("Isabella Brockway", "Naomi Reinke").
friend_("Ismael Camacho", "Jacqueline Butcher").
friend_("Ismael Camacho", "Maude Nagle").
friend_("Jacqueline Butcher", "Johnna Beason").
friend_("Johnna Beason", "Maude Nagle").
friend_("Johnna Beason", "Megan Beason").
friend_("Joshua Gainey", "Pete Gainey").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("warehouse manager").
attribute("sports memorabilia").
attribute("ergonomist").
attribute("audiophile").
attribute("diplomatic services operational officer").
attribute("renaissance fair").
attribute("archaeologist").
attribute("kayaking").
attribute("proofreader").
attribute("horsemanship").
attribute("human resources officer").
attribute("equestrianism").
attribute("accounting technician").
attribute("neuroscience").
attribute("clothing technologist").
attribute("tour skating").
attribute("international aid worker").
attribute("reading").
attribute("stage manager").
attribute("meditation").
attribute("human resources officer").
attribute("satellite watching").
attribute("medical technical officer").
attribute("baseball").
attribute("counselling psychologist").
attribute("stone collecting").
attribute("copy").
attribute("poker").
attribute("doctor").
attribute("slacklining").
attribute("manufacturing systems engineer").
attribute("research").
attribute("structural engineer").
attribute("stone collecting").
attribute("paramedic").
attribute("knowledge/word games").
attribute("medical laboratory scientific officer").
attribute("dog training").
attribute("petroleum engineer").
attribute("scutelliphily").
attribute("environmental health practitioner").
attribute("long-distance running").
attribute("trade mark attorney").
attribute("psychology").
attribute("call centre manager").
attribute("phillumeny").
attribute("financial manager").
attribute("cycling").
attribute("orthoptist").
attribute("stuffed toy collecting").
attribute("consulting civil engineer").
attribute("wrestling").
attribute("conservation officer").
attribute("shoes").
attribute("product development scientist").
attribute("sports memorabilia").
attribute("publishing copy").
attribute("magnet fishing").
attribute("food technologist").
attribute("meditation").
attribute("textile designer").
attribute("beekeeping").
attribute("psychiatrist").
attribute("automobilism").
attribute("publishing rights manager").
attribute("flower collecting and pressing").
attribute("exercise physiologist").
attribute("rock painting").
attribute("energy engineer").
attribute("flying disc").
attribute("field trials officer").
attribute("car tuning").
attribute("sports therapist").
attribute("learning").
attribute("site engineer").
attribute("aerospace").
attribute("health service manager").
attribute("business").
attribute("programmer").
attribute("story writing").
attribute("arboriculturist").
attribute("magnet fishing").
attribute("associate professor").
attribute("social studies").
attribute("merchant navy officer").
attribute("social studies").
attribute("publishing rights manager").
attribute("model racing").
attribute("audiological scientist").
attribute("reading").
attribute("publishing rights manager").
attribute("longboarding").
attribute("biomedical engineer").
attribute("social studies").
attribute("civil engineer").
attribute("microscopy").
attribute("public librarian").
attribute("fossil hunting").
attribute("music tutor").
attribute("publishing").
attribute("financial risk analyst").
attribute("association football").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Abdul Curiel", person).
type("Allie Curiel", person).
type("Allyson Veliz", person).
type("Angel Curiel", person).
type("Antwan Garcia", person).
type("Benny Curiel", person).
type("Bernie Veliz", person).
type("Carrol Nagel", person).
type("Elvie Nagel", person).
type("Florian Irving", person).
type("Gabriele Curiel", person).
type("Jeffery Curiel", person).
type("Kacey Nagel", person).
type("Kennith Curiel", person).
type("Kisha Curiel", person).
type("Leigh Curiel", person).
type("Lucile Curiel", person).
type("Manuela Irving", person).
type("Michael Curiel", person).
type("Miki Garcia", person).
type("Ming Curiel", person).
type("Murray Nagel", person).
type("Nick Curiel", person).
type("Ron Curiel", person).
type("Sharolyn Curiel", person).
type("Tabetha Curiel", person).
type("Adele Butcher", person).
type("Anibal Camacho", person).
type("Blair Gainey", person).
type("Brett Butcher", person).
type("Clayton Butcher", person).
type("Delores Reinke", person).
type("Donovan Brockway", person).
type("Francesca Camacho", person).
type("Frederick Camacho", person).
type("Hank Nagle", person).
type("Isabella Brockway", person).
type("Ismael Camacho", person).
type("Jacqueline Butcher", person).
type("Johnna Beason", person).
type("Joshua Gainey", person).
type("Jules Beason", person).
type("Julian Reinke", person).
type("Loretta Gainey", person).
type("Maude Nagle", person).
type("Megan Beason", person).
type("Naomi Reinke", person).
type("Owen Gainey", person).
type("Pete Gainey", person).
type("Tena Brockway", person).
type("Zana Camacho", person).

:- dynamic dob/2.

dob("Abdul Curiel", "0240-01-13").
dob("Allie Curiel", "0270-11-20").
dob("Allyson Veliz", "0236-09-07").
dob("Angel Curiel", "0329-05-04").
dob("Antwan Garcia", "0208-11-01").
dob("Benny Curiel", "0270-04-03").
dob("Bernie Veliz", "0236-07-10").
dob("Carrol Nagel", "0270-05-06").
dob("Elvie Nagel", "0269-01-26").
dob("Florian Irving", "0237-04-08").
dob("Gabriele Curiel", "0269-11-22").
dob("Jeffery Curiel", "0293-03-07").
dob("Kacey Nagel", "0297-04-17").
dob("Kennith Curiel", "0268-03-10").
dob("Kisha Curiel", "0301-11-13").
dob("Leigh Curiel", "0267-11-25").
dob("Lucile Curiel", "0301-02-13").
dob("Manuela Irving", "0239-07-15").
dob("Michael Curiel", "0302-04-12").
dob("Miki Garcia", "0205-09-09").
dob("Ming Curiel", "0240-04-09").
dob("Murray Nagel", "0303-08-09").
dob("Nick Curiel", "0290-06-11").
dob("Ron Curiel", "0266-04-09").
dob("Sharolyn Curiel", "0297-07-07").
dob("Tabetha Curiel", "0262-05-23").
dob("Adele Butcher", "0215-06-17").
dob("Anibal Camacho", "0296-07-18").
dob("Blair Gainey", "0244-02-24").
dob("Brett Butcher", "0189-04-25").
dob("Clayton Butcher", "0215-06-28").
dob("Delores Reinke", "0191-12-16").
dob("Donovan Brockway", "0250-11-19").
dob("Francesca Camacho", "0239-11-03").
dob("Frederick Camacho", "0237-10-14").
dob("Hank Nagle", "0190-09-22").
dob("Isabella Brockway", "0248-12-20").
dob("Ismael Camacho", "0268-10-18").
dob("Jacqueline Butcher", "0187-11-13").
dob("Johnna Beason", "0246-03-06").
dob("Joshua Gainey", "0268-07-15").
dob("Jules Beason", "0245-11-21").
dob("Julian Reinke", "0164-08-15").
dob("Loretta Gainey", "0220-10-17").
dob("Maude Nagle", "0189-11-25").
dob("Megan Beason", "0272-09-14").
dob("Naomi Reinke", "0162-12-09").
dob("Owen Gainey", "0220-12-14").
dob("Pete Gainey", "0245-01-26").
dob("Tena Brockway", "0279-07-20").
dob("Zana Camacho", "0270-08-24").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Abdul Curiel", "warehouse manager").
job("Allie Curiel", "ergonomist").
job("Allyson Veliz", "diplomatic services operational officer").
job("Angel Curiel", "archaeologist").
job("Antwan Garcia", "proofreader").
job("Benny Curiel", "human resources officer").
job("Bernie Veliz", "accounting technician").
job("Carrol Nagel", "clothing technologist").
job("Elvie Nagel", "international aid worker").
job("Florian Irving", "stage manager").
job("Gabriele Curiel", "human resources officer").
job("Jeffery Curiel", "medical technical officer").
job("Kacey Nagel", "counselling psychologist").
job("Kennith Curiel", "copy").
job("Kisha Curiel", "doctor").
job("Leigh Curiel", "manufacturing systems engineer").
job("Lucile Curiel", "structural engineer").
job("Manuela Irving", "paramedic").
job("Michael Curiel", "medical laboratory scientific officer").
job("Miki Garcia", "petroleum engineer").
job("Ming Curiel", "environmental health practitioner").
job("Murray Nagel", "trade mark attorney").
job("Nick Curiel", "call centre manager").
job("Ron Curiel", "financial manager").
job("Sharolyn Curiel", "orthoptist").
job("Tabetha Curiel", "consulting civil engineer").
job("Adele Butcher", "conservation officer").
job("Anibal Camacho", "product development scientist").
job("Blair Gainey", "publishing copy").
job("Brett Butcher", "food technologist").
job("Clayton Butcher", "textile designer").
job("Delores Reinke", "psychiatrist").
job("Donovan Brockway", "publishing rights manager").
job("Francesca Camacho", "exercise physiologist").
job("Frederick Camacho", "energy engineer").
job("Hank Nagle", "field trials officer").
job("Isabella Brockway", "sports therapist").
job("Ismael Camacho", "site engineer").
job("Jacqueline Butcher", "health service manager").
job("Johnna Beason", "programmer").
job("Joshua Gainey", "arboriculturist").
job("Jules Beason", "associate professor").
job("Julian Reinke", "merchant navy officer").
job("Loretta Gainey", "publishing rights manager").
job("Maude Nagle", "audiological scientist").
job("Megan Beason", "publishing rights manager").
job("Naomi Reinke", "biomedical engineer").
job("Owen Gainey", "civil engineer").
job("Pete Gainey", "public librarian").
job("Tena Brockway", "music tutor").
job("Zana Camacho", "financial risk analyst").

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

hobby("Abdul Curiel", "sports memorabilia").
hobby("Allie Curiel", "audiophile").
hobby("Allyson Veliz", "renaissance fair").
hobby("Angel Curiel", "kayaking").
hobby("Antwan Garcia", "horsemanship").
hobby("Benny Curiel", "equestrianism").
hobby("Bernie Veliz", "neuroscience").
hobby("Carrol Nagel", "tour skating").
hobby("Elvie Nagel", "reading").
hobby("Florian Irving", "meditation").
hobby("Gabriele Curiel", "satellite watching").
hobby("Jeffery Curiel", "baseball").
hobby("Kacey Nagel", "stone collecting").
hobby("Kennith Curiel", "poker").
hobby("Kisha Curiel", "slacklining").
hobby("Leigh Curiel", "research").
hobby("Lucile Curiel", "stone collecting").
hobby("Manuela Irving", "knowledge/word games").
hobby("Michael Curiel", "dog training").
hobby("Miki Garcia", "scutelliphily").
hobby("Ming Curiel", "long-distance running").
hobby("Murray Nagel", "psychology").
hobby("Nick Curiel", "phillumeny").
hobby("Ron Curiel", "cycling").
hobby("Sharolyn Curiel", "stuffed toy collecting").
hobby("Tabetha Curiel", "wrestling").
hobby("Adele Butcher", "shoes").
hobby("Anibal Camacho", "sports memorabilia").
hobby("Blair Gainey", "magnet fishing").
hobby("Brett Butcher", "meditation").
hobby("Clayton Butcher", "beekeeping").
hobby("Delores Reinke", "automobilism").
hobby("Donovan Brockway", "flower collecting and pressing").
hobby("Francesca Camacho", "rock painting").
hobby("Frederick Camacho", "flying disc").
hobby("Hank Nagle", "car tuning").
hobby("Isabella Brockway", "learning").
hobby("Ismael Camacho", "aerospace").
hobby("Jacqueline Butcher", "business").
hobby("Johnna Beason", "story writing").
hobby("Joshua Gainey", "magnet fishing").
hobby("Jules Beason", "social studies").
hobby("Julian Reinke", "social studies").
hobby("Loretta Gainey", "model racing").
hobby("Maude Nagle", "reading").
hobby("Megan Beason", "longboarding").
hobby("Naomi Reinke", "social studies").
hobby("Owen Gainey", "microscopy").
hobby("Pete Gainey", "fossil hunting").
hobby("Tena Brockway", "publishing").
hobby("Zana Camacho", "association football").

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
