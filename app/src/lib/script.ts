// Reading script for voice capture. Varied length and tone gives the
// model a fuller picture of the voice than free rambling. Plain, neutral
// sentences with numbers, questions, and a range of vowels and cadence.
//
// Long enough to cover the unlock target (CADENCE_VOICE_UNLOCK_SECONDS,
// ten minutes by default) in a single pass. Reading the same handful of
// lines over and over flattens delivery, which is exactly what the model
// should not learn. The groups below are deliberate: statements, questions,
// counting, clipped fragments and long flowing sentences each stretch a
// different part of the voice.

export const READING_SCRIPT: string[] = [
  // Opening, easy and unhurried.
  "Hello. This is my voice, recorded plainly, with nothing clever about it.",
  "I am going to read for a while, and none of it needs to be perfect.",

  // Everyday and neutral.
  "Please leave the parcel behind the blue bin if nobody answers the door.",
  "The library closes at six, but the reading room stays open a little later.",
  "Turn left at the roundabout, then follow the signs for the coast.",
  "There is bread in the freezer and soup in the pan, if you get hungry.",
  "I will water the plants on Thursday and feed the cat on Friday.",
  "Bread, butter, coffee, and a spare umbrella sat by the door, waiting for someone to remember them.",
  "He folded the map along its old creases and pushed it back into the glove compartment.",
  "We should leave before the traffic starts, or we will be sitting on the bypass for an hour.",
  "The kettle boiled twice because I forgot about it the first time.",
  "Everything in the drawer belonged to someone else, and none of it was worth keeping.",

  // Description, longer and flowing.
  "The morning train rolled slowly through the valley, and the fields were still wet from last night's rain.",
  "She kept a notebook of half-finished ideas, scribbled between meetings and long bus rides home.",
  "The engine hummed beneath the floorboards like a patient animal waiting for spring to arrive.",
  "The harbour emptied at dusk, and the boats knocked gently against the wooden posts.",
  "Snow settled on the roof tiles overnight, softening every hard edge the town had.",
  "Somewhere below the window, a cyclist rang a bell twice and vanished around the corner.",
  "The orchard smelled of cut grass and warm apples, and nobody wanted to go inside.",
  "Long shadows crossed the courtyard, and the stones gave back the heat they had gathered all day.",
  "A single lamp burned in the upstairs window, steady as a held note.",
  "Autumn arrived quietly this year, without any of its usual announcements.",
  "The river ran high and brown after the storm, carrying branches and bright plastic.",
  "Dust turned slowly in the light between the shutters, going nowhere in particular.",
  "By the time the last guest left, the candles had burned down to nothing and somebody had stacked every chair in the wrong place.",
  "If you follow the path past the second gate and keep the hedge on your right, you will come out exactly where you started, which is the joke of it.",
  "The recording caught the room as much as the voice: the hum of the fridge, a car outside, the small creak of a chair.",

  // Questions, for the lift at the end of a phrase.
  "Would you have waited at the station if you had known the timetable was wrong?",
  "Is it seven o'clock already? I thought we had at least another hour before the light went.",
  "Have you ever noticed how a room sounds different once the furniture is gone?",
  "What would you say if I told you the whole thing was recorded in one take?",
  "Should we start again from the top, or keep the version we already have?",
  "Why does every clock in this house disagree by a minute or two?",
  "Are you certain that is the right key, or does it only feel familiar?",
  "Could you hear the difference, or was it always just in my head?",
  "How many times can a phrase repeat before it stops meaning anything?",
  "Do you want the long answer, or the one that fits on a postcard?",

  // Counting and precision.
  "One, two, three, four, five. I count them out slowly, then a little faster: six, seven, eight, nine, ten.",
  "Twenty-one, thirty-four, fifty-five, eighty-nine. Each number is the two before it added together.",
  "It costs nineteen pounds and ninety-nine pence, which is almost twenty, but not quite.",
  "Set the timer for three minutes and forty seconds, then take it off the heat.",
  "Between nineteen ninety and two thousand and five, the whole street was rebuilt twice.",
  "Call back after half past four, or leave a message and I will find you tomorrow.",
  "The third of March, the ninth of July, and the last Friday in November.",

  // Clipped fragments, held apart.
  "Bright light. Deep water. A quiet room. Short phrases, held apart, each one landing on its own.",
  "Stop. Listen. Nothing. Good.",
  "Salt. Pepper. Oil. Flour. Four things, and a bowl to put them in.",
  "Yes. No. Maybe. Ask me again in the morning.",
  "Up the stairs. Down the hall. Second door on the left.",
  "Cold hands. Warm mug. Long silence. That was the whole evening.",

  // Warmth and dry humour, for range.
  "I kept your letter for years, and I still cannot explain exactly why.",
  "It was the kind of joke that only worked because everyone was tired.",
  "She laughed before the sentence was finished, which is how you know it landed.",
  "There is a particular comfort in hearing the same song at the end of a long week.",
  "We were not lost, exactly. We simply had no idea where we were.",
  "The instructions were clear, thorough, and completely wrong.",
  "Apparently the meeting could have been an email after all.",
  "I am told this is the simplest possible way to do it, which is a little worrying.",
  "Tomorrow we will record everything again, and it will probably sound completely different.",

  // Consonants and clusters, for articulation.
  "Six thick planks, stacked square, shifted slightly when the wind picked up.",
  "The judge urged the jury to weigh each charge slowly and separately.",
  "Fresh thyme, crushed garlic, and a splash of white vinegar finished the dish.",
  "Which switch did she choose, and why does the chandelier still flicker?",
  "Brisk breezes brushed the bright beach, and the children shrieked and scattered.",
  "He whispered through the doorway, then shouted from the far end of the hall.",
  "Twelve strong swimmers crossed the cold channel and slept for a day afterwards.",

  // Music, since that is what the voice is for.
  "A cadence is simply the way a phrase comes to rest, like footsteps slowing as they reach a door.",
  "Hum the melody first, then worry about the words that go on top of it.",
  "The chorus should feel inevitable, as though it was always going to arrive.",
  "Count us in: one, two, a one, two, three, four.",
  "Every song is a small argument between the rhythm and the words.",
  "Hold that note a beat longer than feels comfortable, then let it fall.",
  "The bass moves once, and the whole chord means something else.",
  "Sing it quietly first. The loud version can wait until you believe it.",

  // Closing.
  "That is enough for now. Whatever the voice does next, it starts from here.",
];
