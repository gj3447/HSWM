
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

parent("Alden Faber", "Bethany Faber").
parent("Alden Faber", "Lyndon Faber").
parent("Bethany Faber", "Ambrose Shields").
parent("Bethany Faber", "Debbie Shields").
parent("Catina Faber", "Tammie Mcwhorter").
parent("Catina Faber", "Vito Mcwhorter").
parent("Charity Faber", "Francis Vanpelt").
parent("Charity Faber", "Shelly Vanpelt").
parent("Debbie Shields", "Derek Burke").
parent("Debbie Shields", "Dollie Burke").
parent("Edwin Faber", "Bethany Faber").
parent("Edwin Faber", "Lyndon Faber").
parent("Elias Mcwhorter", "Tammie Mcwhorter").
parent("Elias Mcwhorter", "Vito Mcwhorter").
parent("Logan Faber", "Alden Faber").
parent("Logan Faber", "Catina Faber").
parent("Lyndon Faber", "Essie Faber").
parent("Lyndon Faber", "Eugenio Faber").
parent("Maryann Faber", "Alden Faber").
parent("Maryann Faber", "Catina Faber").
parent("Neil Faber", "Alden Faber").
parent("Neil Faber", "Catina Faber").
parent("Pamula Mcwhorter", "Elias Mcwhorter").
parent("Pamula Mcwhorter", "Natasha Mcwhorter").
parent("Rob Faber", "Bethany Faber").
parent("Rob Faber", "Lyndon Faber").
parent("Stevie Shields", "Ambrose Shields").
parent("Stevie Shields", "Debbie Shields").
parent("Timmy Faber", "Charity Faber").
parent("Timmy Faber", "Rob Faber").
parent("Vanessa Faber", "Bethany Faber").
parent("Vanessa Faber", "Lyndon Faber").
parent("Brigida Healey", "Jeffery Healey").
parent("Brigida Healey", "Theda Healey").
parent("Charmain Kimball", "Isabell Kimball").
parent("Charmain Kimball", "Philip Kimball").
parent("Danilo Healey", "Jeffery Healey").
parent("Danilo Healey", "Theda Healey").
parent("Debi Drayton", "Allen Healey").
parent("Debi Drayton", "Enid Healey").
parent("Deirdre Kimball", "Isabell Kimball").
parent("Deirdre Kimball", "Philip Kimball").
parent("Delbert Kimball", "Isabell Kimball").
parent("Delbert Kimball", "Philip Kimball").
parent("Demetrius Rauch", "Junior Rauch").
parent("Demetrius Rauch", "Naomi Rauch").
parent("Heather Healey", "Jeffery Healey").
parent("Heather Healey", "Theda Healey").
parent("Isabell Kimball", "Jeffery Healey").
parent("Isabell Kimball", "Theda Healey").
parent("Jeffery Healey", "Allen Healey").
parent("Jeffery Healey", "Enid Healey").
parent("Naomi Rauch", "Isabell Kimball").
parent("Naomi Rauch", "Philip Kimball").
parent("Phil Drayton", "Debi Drayton").
parent("Phil Drayton", "Lon Drayton").
parent("Philip Kimball", "Abe Kimball").
parent("Philip Kimball", "Ione Kimball").
parent("Reyes Kimball", "Isabell Kimball").
parent("Reyes Kimball", "Philip Kimball").
parent("Rosemarie Rauch", "Junior Rauch").
parent("Rosemarie Rauch", "Naomi Rauch").
parent("Theda Healey", "Antionette Parrott").
parent("Theda Healey", "Harvey Parrott").
parent("Viva Healey", "Jeffery Healey").
parent("Viva Healey", "Theda Healey").

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

gender("Alden Faber", "male").
gender("Ambrose Shields", "male").
gender("Bethany Faber", "female").
gender("Catina Faber", "female").
gender("Charity Faber", "female").
gender("Debbie Shields", "female").
gender("Derek Burke", "male").
gender("Dollie Burke", "female").
gender("Edwin Faber", "male").
gender("Elias Mcwhorter", "male").
gender("Essie Faber", "female").
gender("Eugenio Faber", "male").
gender("Francis Vanpelt", "male").
gender("Logan Faber", "male").
gender("Lyndon Faber", "male").
gender("Maryann Faber", "female").
gender("Natasha Mcwhorter", "female").
gender("Neil Faber", "male").
gender("Pamula Mcwhorter", "female").
gender("Rob Faber", "male").
gender("Shelly Vanpelt", "female").
gender("Stevie Shields", "male").
gender("Tammie Mcwhorter", "female").
gender("Timmy Faber", "male").
gender("Vanessa Faber", "female").
gender("Vito Mcwhorter", "male").
gender("Abe Kimball", "male").
gender("Allen Healey", "male").
gender("Antionette Parrott", "female").
gender("Brigida Healey", "female").
gender("Charmain Kimball", "female").
gender("Danilo Healey", "male").
gender("Debi Drayton", "female").
gender("Deirdre Kimball", "female").
gender("Delbert Kimball", "male").
gender("Demetrius Rauch", "male").
gender("Enid Healey", "female").
gender("Harvey Parrott", "male").
gender("Heather Healey", "female").
gender("Ione Kimball", "female").
gender("Isabell Kimball", "female").
gender("Jeffery Healey", "male").
gender("Junior Rauch", "male").
gender("Lon Drayton", "male").
gender("Naomi Rauch", "female").
gender("Phil Drayton", "male").
gender("Philip Kimball", "male").
gender("Reyes Kimball", "male").
gender("Rosemarie Rauch", "female").
gender("Theda Healey", "female").
gender("Viva Healey", "female").

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

friend_("Alden Faber", "Catina Faber").
friend_("Alden Faber", "Derek Burke").
friend_("Alden Faber", "Vito Mcwhorter").
friend_("Alden Faber", "Junior Rauch").
friend_("Alden Faber", "Philip Kimball").
friend_("Bethany Faber", "Derek Burke").
friend_("Bethany Faber", "Edwin Faber").
friend_("Bethany Faber", "Maryann Faber").
friend_("Bethany Faber", "Deirdre Kimball").
friend_("Bethany Faber", "Junior Rauch").
friend_("Catina Faber", "Demetrius Rauch").
friend_("Charity Faber", "Rob Faber").
friend_("Charity Faber", "Antionette Parrott").
friend_("Charity Faber", "Naomi Rauch").
friend_("Charity Faber", "Theda Healey").
friend_("Debbie Shields", "Danilo Healey").
friend_("Derek Burke", "Francis Vanpelt").
friend_("Derek Burke", "Timmy Faber").
friend_("Derek Burke", "Vanessa Faber").
friend_("Dollie Burke", "Isabell Kimball").
friend_("Edwin Faber", "Rob Faber").
friend_("Edwin Faber", "Allen Healey").
friend_("Edwin Faber", "Harvey Parrott").
friend_("Edwin Faber", "Ione Kimball").
friend_("Elias Mcwhorter", "Stevie Shields").
friend_("Elias Mcwhorter", "Vanessa Faber").
friend_("Elias Mcwhorter", "Jeffery Healey").
friend_("Elias Mcwhorter", "Theda Healey").
friend_("Essie Faber", "Rob Faber").
friend_("Essie Faber", "Shelly Vanpelt").
friend_("Eugenio Faber", "Neil Faber").
friend_("Eugenio Faber", "Allen Healey").
friend_("Eugenio Faber", "Danilo Healey").
friend_("Francis Vanpelt", "Stevie Shields").
friend_("Francis Vanpelt", "Brigida Healey").
friend_("Francis Vanpelt", "Deirdre Kimball").
friend_("Lyndon Faber", "Maryann Faber").
friend_("Lyndon Faber", "Rob Faber").
friend_("Lyndon Faber", "Tammie Mcwhorter").
friend_("Lyndon Faber", "Reyes Kimball").
friend_("Maryann Faber", "Antionette Parrott").
friend_("Maryann Faber", "Junior Rauch").
friend_("Natasha Mcwhorter", "Heather Healey").
friend_("Natasha Mcwhorter", "Theda Healey").
friend_("Natasha Mcwhorter", "Viva Healey").
friend_("Neil Faber", "Timmy Faber").
friend_("Neil Faber", "Isabell Kimball").
friend_("Pamula Mcwhorter", "Deirdre Kimball").
friend_("Pamula Mcwhorter", "Viva Healey").
friend_("Rob Faber", "Charmain Kimball").
friend_("Shelly Vanpelt", "Danilo Healey").
friend_("Shelly Vanpelt", "Delbert Kimball").
friend_("Stevie Shields", "Enid Healey").
friend_("Stevie Shields", "Phil Drayton").
friend_("Tammie Mcwhorter", "Brigida Healey").
friend_("Tammie Mcwhorter", "Deirdre Kimball").
friend_("Timmy Faber", "Delbert Kimball").
friend_("Timmy Faber", "Demetrius Rauch").
friend_("Timmy Faber", "Isabell Kimball").
friend_("Timmy Faber", "Junior Rauch").
friend_("Timmy Faber", "Reyes Kimball").
friend_("Vito Mcwhorter", "Lon Drayton").
friend_("Abe Kimball", "Junior Rauch").
friend_("Allen Healey", "Debi Drayton").
friend_("Allen Healey", "Isabell Kimball").
friend_("Antionette Parrott", "Harvey Parrott").
friend_("Brigida Healey", "Charmain Kimball").
friend_("Brigida Healey", "Harvey Parrott").
friend_("Charmain Kimball", "Demetrius Rauch").
friend_("Charmain Kimball", "Reyes Kimball").
friend_("Danilo Healey", "Viva Healey").
friend_("Debi Drayton", "Naomi Rauch").
friend_("Deirdre Kimball", "Viva Healey").
friend_("Delbert Kimball", "Viva Healey").
friend_("Demetrius Rauch", "Viva Healey").
friend_("Enid Healey", "Philip Kimball").
friend_("Harvey Parrott", "Viva Healey").
friend_("Heather Healey", "Lon Drayton").
friend_("Ione Kimball", "Philip Kimball").
friend_("Philip Kimball", "Reyes Kimball").
friend_("Reyes Kimball", "Rosemarie Rauch").
friend_("Reyes Kimball", "Viva Healey").

granddaughter(X, Y) :-
    grandchild(X, Y),
    female(Y).

:- dynamic goal_expansion/2.
:- multifile goal_expansion/2.


grandchild(X, Y) :-
    grandparent(Y, X).

:- dynamic attribute/1.

attribute("hydrologist").
attribute("australian rules football").
attribute("secondary school teacher").
attribute("insect collecting").
attribute("publishing rights manager").
attribute("backgammon").
attribute("financial risk analyst").
attribute("figure skating").
attribute("environmental education officer").
attribute("herping").
attribute("broadcast presenter").
attribute("metal detecting").
attribute("international aid worker").
attribute("trainspotting").
attribute("planning and development surveyor").
attribute("lotology").
attribute("chiropractor").
attribute("animal fancy").
attribute("chiropractor").
attribute("car riding").
attribute("chief operating officer").
attribute("race walking").
attribute("dispensing optician").
attribute("badminton").
attribute("theatre manager").
attribute("sociology").
attribute("tourist information centre manager").
attribute("fishkeeping").
attribute("site engineer").
attribute("die-cast toy").
attribute("film editor").
attribute("public transport riding").
attribute("purchasing manager").
attribute("slot car").
attribute("chief of staff").
attribute("meditation").
attribute("ophthalmologist").
attribute("finance").
attribute("clinical psychologist").
attribute("geocaching").
attribute("higher education lecturer").
attribute("antiquities").
attribute("accounting technician").
attribute("hobby tunneling").
attribute("professor emeritus").
attribute("geocaching").
attribute("secondary school teacher").
attribute("shortwave listening").
attribute("librarian").
attribute("learning").
attribute("IT consultant").
attribute("vintage cars").
attribute("contractor").
attribute("digital hoarding").
attribute("biomedical scientist").
attribute("philately").
attribute("scientist").
attribute("meditation").
attribute("technical author").
attribute("amateur astronomy").
attribute("ophthalmologist").
attribute("iceboat racing").
attribute("government social research officer").
attribute("benchmarking").
attribute("chief executive officer").
attribute("animal fancy").
attribute("paramedic").
attribute("fishkeeping").
attribute("psychiatric nurse").
attribute("slot car racing").
attribute("pilot").
attribute("volleyball").
attribute("speech and language therapist").
attribute("research").
attribute("environmental education officer").
attribute("meteorology").
attribute("firefighter").
attribute("tether car").
attribute("dance movement psychotherapist").
attribute("meteorology").
attribute("media planner").
attribute("scutelliphily").
attribute("estate manager").
attribute("podcast hosting").
attribute("publishing copy").
attribute("research").
attribute("graphic designer").
attribute("tea bag collecting").
attribute("barista").
attribute("railway studies").
attribute("airline pilot").
attribute("figure skating").
attribute("radiation protection practitioner").
attribute("video game collecting").
attribute("actor").
attribute("exhibition drill").
attribute("retail buyer").
attribute("poker").
attribute("training and development officer").
attribute("art collecting").
attribute("exhibition designer").
attribute("picnicking").

great_uncle(X, Y) :-
    grandparent(X, A),
    brother(A, Y).

:- dynamic type/2.

type("Alden Faber", person).
type("Ambrose Shields", person).
type("Bethany Faber", person).
type("Catina Faber", person).
type("Charity Faber", person).
type("Debbie Shields", person).
type("Derek Burke", person).
type("Dollie Burke", person).
type("Edwin Faber", person).
type("Elias Mcwhorter", person).
type("Essie Faber", person).
type("Eugenio Faber", person).
type("Francis Vanpelt", person).
type("Logan Faber", person).
type("Lyndon Faber", person).
type("Maryann Faber", person).
type("Natasha Mcwhorter", person).
type("Neil Faber", person).
type("Pamula Mcwhorter", person).
type("Rob Faber", person).
type("Shelly Vanpelt", person).
type("Stevie Shields", person).
type("Tammie Mcwhorter", person).
type("Timmy Faber", person).
type("Vanessa Faber", person).
type("Vito Mcwhorter", person).
type("Abe Kimball", person).
type("Allen Healey", person).
type("Antionette Parrott", person).
type("Brigida Healey", person).
type("Charmain Kimball", person).
type("Danilo Healey", person).
type("Debi Drayton", person).
type("Deirdre Kimball", person).
type("Delbert Kimball", person).
type("Demetrius Rauch", person).
type("Enid Healey", person).
type("Harvey Parrott", person).
type("Heather Healey", person).
type("Ione Kimball", person).
type("Isabell Kimball", person).
type("Jeffery Healey", person).
type("Junior Rauch", person).
type("Lon Drayton", person).
type("Naomi Rauch", person).
type("Phil Drayton", person).
type("Philip Kimball", person).
type("Reyes Kimball", person).
type("Rosemarie Rauch", person).
type("Theda Healey", person).
type("Viva Healey", person).

:- dynamic dob/2.

dob("Alden Faber", "0266-10-15").
dob("Ambrose Shields", "0217-04-07").
dob("Bethany Faber", "0242-01-16").
dob("Catina Faber", "0269-06-21").
dob("Charity Faber", "0269-06-09").
dob("Debbie Shields", "0215-05-03").
dob("Derek Burke", "0188-09-27").
dob("Dollie Burke", "0189-08-28").
dob("Edwin Faber", "0271-03-16").
dob("Elias Mcwhorter", "0276-06-15").
dob("Essie Faber", "0212-08-10").
dob("Eugenio Faber", "0212-03-15").
dob("Francis Vanpelt", "0242-08-22").
dob("Logan Faber", "0294-10-22").
dob("Lyndon Faber", "0239-03-17").
dob("Maryann Faber", "0299-11-30").
dob("Natasha Mcwhorter", "0276-01-18").
dob("Neil Faber", "0295-12-08").
dob("Pamula Mcwhorter", "0298-12-04").
dob("Rob Faber", "0270-03-09").
dob("Shelly Vanpelt", "0244-05-02").
dob("Stevie Shields", "0236-04-15").
dob("Tammie Mcwhorter", "0242-02-01").
dob("Timmy Faber", "0300-10-31").
dob("Vanessa Faber", "0263-08-14").
dob("Vito Mcwhorter", "0239-12-23").
dob("Abe Kimball", "0258-02-22").
dob("Allen Healey", "0233-12-19").
dob("Antionette Parrott", "0242-02-14").
dob("Brigida Healey", "0294-01-10").
dob("Charmain Kimball", "0315-05-24").
dob("Danilo Healey", "0296-10-14").
dob("Debi Drayton", "0265-04-23").
dob("Deirdre Kimball", "0316-07-20").
dob("Delbert Kimball", "0321-12-02").
dob("Demetrius Rauch", "0342-07-22").
dob("Enid Healey", "0232-05-19").
dob("Harvey Parrott", "0241-01-17").
dob("Heather Healey", "0296-10-14").
dob("Ione Kimball", "0257-06-27").
dob("Isabell Kimball", "0290-10-03").
dob("Jeffery Healey", "0266-10-03").
dob("Junior Rauch", "0313-05-01").
dob("Lon Drayton", "0264-06-05").
dob("Naomi Rauch", "0316-07-20").
dob("Phil Drayton", "0292-08-21").
dob("Philip Kimball", "0288-08-10").
dob("Reyes Kimball", "0318-07-11").
dob("Rosemarie Rauch", "0337-03-07").
dob("Theda Healey", "0269-01-27").
dob("Viva Healey", "0294-11-08").

great_aunt(X, Y) :-
    grandparent(X, A),
    sister(A, Y).

:- dynamic message_hook/3.
:- multifile message_hook/3.


:- dynamic job/2.

job("Alden Faber", "hydrologist").
job("Ambrose Shields", "secondary school teacher").
job("Bethany Faber", "publishing rights manager").
job("Catina Faber", "financial risk analyst").
job("Charity Faber", "environmental education officer").
job("Debbie Shields", "broadcast presenter").
job("Derek Burke", "international aid worker").
job("Dollie Burke", "planning and development surveyor").
job("Edwin Faber", "chiropractor").
job("Elias Mcwhorter", "chiropractor").
job("Essie Faber", "chief operating officer").
job("Eugenio Faber", "dispensing optician").
job("Francis Vanpelt", "theatre manager").
job("Logan Faber", "tourist information centre manager").
job("Lyndon Faber", "site engineer").
job("Maryann Faber", "film editor").
job("Natasha Mcwhorter", "purchasing manager").
job("Neil Faber", "chief of staff").
job("Pamula Mcwhorter", "ophthalmologist").
job("Rob Faber", "clinical psychologist").
job("Shelly Vanpelt", "higher education lecturer").
job("Stevie Shields", "accounting technician").
job("Tammie Mcwhorter", "professor emeritus").
job("Timmy Faber", "secondary school teacher").
job("Vanessa Faber", "librarian").
job("Vito Mcwhorter", "IT consultant").
job("Abe Kimball", "contractor").
job("Allen Healey", "biomedical scientist").
job("Antionette Parrott", "scientist").
job("Brigida Healey", "technical author").
job("Charmain Kimball", "ophthalmologist").
job("Danilo Healey", "government social research officer").
job("Debi Drayton", "chief executive officer").
job("Deirdre Kimball", "paramedic").
job("Delbert Kimball", "psychiatric nurse").
job("Demetrius Rauch", "pilot").
job("Enid Healey", "speech and language therapist").
job("Harvey Parrott", "environmental education officer").
job("Heather Healey", "firefighter").
job("Ione Kimball", "dance movement psychotherapist").
job("Isabell Kimball", "media planner").
job("Jeffery Healey", "estate manager").
job("Junior Rauch", "publishing copy").
job("Lon Drayton", "graphic designer").
job("Naomi Rauch", "barista").
job("Phil Drayton", "airline pilot").
job("Philip Kimball", "radiation protection practitioner").
job("Reyes Kimball", "actor").
job("Rosemarie Rauch", "retail buyer").
job("Theda Healey", "training and development officer").
job("Viva Healey", "exhibition designer").

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

hobby("Alden Faber", "australian rules football").
hobby("Ambrose Shields", "insect collecting").
hobby("Bethany Faber", "backgammon").
hobby("Catina Faber", "figure skating").
hobby("Charity Faber", "herping").
hobby("Debbie Shields", "metal detecting").
hobby("Derek Burke", "trainspotting").
hobby("Dollie Burke", "lotology").
hobby("Edwin Faber", "animal fancy").
hobby("Elias Mcwhorter", "car riding").
hobby("Essie Faber", "race walking").
hobby("Eugenio Faber", "badminton").
hobby("Francis Vanpelt", "sociology").
hobby("Logan Faber", "fishkeeping").
hobby("Lyndon Faber", "die-cast toy").
hobby("Maryann Faber", "public transport riding").
hobby("Natasha Mcwhorter", "slot car").
hobby("Neil Faber", "meditation").
hobby("Pamula Mcwhorter", "finance").
hobby("Rob Faber", "geocaching").
hobby("Shelly Vanpelt", "antiquities").
hobby("Stevie Shields", "hobby tunneling").
hobby("Tammie Mcwhorter", "geocaching").
hobby("Timmy Faber", "shortwave listening").
hobby("Vanessa Faber", "learning").
hobby("Vito Mcwhorter", "vintage cars").
hobby("Abe Kimball", "digital hoarding").
hobby("Allen Healey", "philately").
hobby("Antionette Parrott", "meditation").
hobby("Brigida Healey", "amateur astronomy").
hobby("Charmain Kimball", "iceboat racing").
hobby("Danilo Healey", "benchmarking").
hobby("Debi Drayton", "animal fancy").
hobby("Deirdre Kimball", "fishkeeping").
hobby("Delbert Kimball", "slot car racing").
hobby("Demetrius Rauch", "volleyball").
hobby("Enid Healey", "research").
hobby("Harvey Parrott", "meteorology").
hobby("Heather Healey", "tether car").
hobby("Ione Kimball", "meteorology").
hobby("Isabell Kimball", "scutelliphily").
hobby("Jeffery Healey", "podcast hosting").
hobby("Junior Rauch", "research").
hobby("Lon Drayton", "tea bag collecting").
hobby("Naomi Rauch", "railway studies").
hobby("Phil Drayton", "figure skating").
hobby("Philip Kimball", "video game collecting").
hobby("Reyes Kimball", "exhibition drill").
hobby("Rosemarie Rauch", "poker").
hobby("Theda Healey", "art collecting").
hobby("Viva Healey", "picnicking").

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
