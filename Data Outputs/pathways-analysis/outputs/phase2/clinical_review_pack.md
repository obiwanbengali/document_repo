# Candidate Bayesian family review pack

Generated 2026-11-04 17:46 UTC. Candidate set: `hybrid_a`, 34 families over 815 active pathways.

## What we are asking

We have grouped NHS Pathways into candidate families using measured structure: which pathways transfer to one another, and which share questions, symptom discriminators, SNOMED concepts and dispositions. **Structure cannot tell us whether a group is clinically sensible.** That is what this review is for.

For each family below, please tell us:

1. Is this recognisable as one clinical area? If not, what should it be called, or how should it be divided?
2. Are any of the listed pathways in the wrong family?
3. Where a family overlaps strongly with another, are they one area or two?
4. Are there safety-critical routes into or out of this family that must not be broken by separating it from another?

Nothing here is a decision. No architecture has been chosen.

---

## HA_C00 — Family_00

**123 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Nail Injury | Lower Back Injury, Penetrating | Abdominal or Flank Injury, Penetrating
- **Dominant clinical areas:** hip & leg | arm | back
- **Representative pathways:** PW1576 Bites, Human; PW1586 Bites, Human; PW1408 Genital Injury, Penetrating; PW835 Genital Injury, Penetrating; PW1259 Skin, Minor Foreign Body; PW1328 Skin, Minor Foreign Body
- **Most common symptom discriminators:** 4052 ED full ED assessment and management capability — 92 of this family's pathways, 377 estate-wide; 4003 PC full Primary Care assessment and prescribing capability — 91 of this family's pathways, 514 estate-wide; 4010 ALL assault, sexual — 61 of this family's pathways, 160 estate-wide; 4004 AMB foreign body, wound, large — 28 of this family's pathways, 38 estate-wide; 4033 AMB new/worsening breathlessness — 28 of this family's pathways, 123 estate-wide; 4005 AMB ischaemia, post trauma — 18 of this family's pathways, 18 estate-wide; 4501 ED Ischaemia, post trauma — 18 of this family's pathways, 18 estate-wide; 4017 AMB gastrointestinal bleed — 17 of this family's pathways, 82 estate-wide
- **Most common SNOMED concepts:** 422608009 Sexual assault — 60 of this family's pathways, 160 estate-wide; 90774003 Victim of physical assault — 59 of this family's pathways, 125 estate-wide; 103001002 Feeling feverish — 58 of this family's pathways, 322 estate-wide; 262519004 Multiple injuries — 42 of this family's pathways, 68 estate-wide; 239161005 Wound haemorrhage — 37 of this family's pathways, 47 estate-wide; 262557004 Deep wound — 36 of this family's pathways, 40 estate-wide; 48422000 Open wound with complication — 36 of this family's pathways, 40 estate-wide; 267036007 Dyspnoea — 35 of this family's pathways, 223 estate-wide
- **Strongest overlaps:** HA_C04_01 (shared SNOMED concepts, Jaccard 0.32); HA_C02 (shared SNOMED concepts, Jaccard 0.31); HA_C01_00 (shared SNOMED concepts, Jaccard 0.30)
- **Major boundary pathways:** PT31 Non-emergency Ambulance Closure, Trauma (strong boundary pathway, 10 external links); PW596 Chest or Upper Back Injury, Penetrating (strong boundary pathway, 8 external links); PW580 Burn, Thermal (strong boundary pathway, 8 external links); PW1066 Wound Problems (strong boundary pathway, 8 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C04_01 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
5. This is one of the larger families. Does it contain more than one clinical area that should be separated?

---

## HA_C02 — Family_01

**106 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Lower Limb Pain or Swelling | Easy or Unexplained Bruising | Constipation
- **Dominant clinical areas:** not area specific | arm | hip & leg
- **Representative pathways:** PW1626 Wrist, Hand or Finger Pain or Swelling; PW1141 Shoulder Pain; PW1143 Shoulder Pain; PW1167 Arm Pain or Swelling; PW923 Arm Pain or Swelling; PW732 Groin Pain or Groin Swelling
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 88 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 50 of this family's pathways, 377 estate-wide; 4027 AMB ischaemia, non-trauma — 30 of this family's pathways, 48 estate-wide; 4000 AMB septicaemia — 27 of this family's pathways, 158 estate-wide; 4033 AMB new/worsening breathlessness — 23 of this family's pathways, 123 estate-wide; 4002 AMB meningitis — 21 of this family's pathways, 140 estate-wide; 4026 AMB deep vein thrombosis — 21 of this family's pathways, 39 estate-wide; 4029 AMB spinal cord compression — 16 of this family's pathways, 29 estate-wide
- **Most common SNOMED concepts:** 103001002 Feeling feverish — 64 of this family's pathways, 322 estate-wide; 266712008 New medication commenced — 42 of this family's pathways, 105 estate-wide; 213257006 Generally unwell — 41 of this family's pathways, 142 estate-wide; 182877009 Drug dosage altered — 39 of this family's pathways, 99 estate-wide; 275723000 Patient's condition deteriorating — 39 of this family's pathways, 216 estate-wide; 128482007 Acute inflammatory disease — 36 of this family's pathways, 57 estate-wide; 247441003 Erythema — 36 of this family's pathways, 60 estate-wide; 707793005 Hot skin — 36 of this family's pathways, 57 estate-wide
- **Strongest overlaps:** HA_C06 (shared SNOMED concepts, Jaccard 0.44); HA_C05 (shared SNOMED concepts, Jaccard 0.42); HA_C03 (shared SNOMED concepts, Jaccard 0.41)
- **Major boundary pathways:** PW1804 Unwell Infant (cross-family hub, 6 external links); PT5 Medication (strong boundary pathway, 60 external links); PA87 Cardiac Medication Closure (strong boundary pathway, 26 external links); PW1345 Other Symptoms (strong boundary pathway, 9 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C06 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
5. This is one of the larger families. Does it contain more than one clinical area that should be separated?

---

## HA_C03 — Family_02

**94 pathways.** Named from: neutral. Structural cohesion: high (graph and clinical-feature evidence agree).

- **Dominant symptom groups:** Diarrhoea and Vomiting | Diarrhoea | Vomiting
- **Dominant clinical areas:** abdomen | mouth | chest
- **Representative pathways:** PW1563 Diarrhoea and Vomiting; PW630 Diarrhoea; PW518 Abdominal, Flank, Groin or Back Pain or Swelling; PW521 Abdominal, Flank, Groin or Back Pain or Swelling; PW938 Vomiting and/or Nausea; PW1832 Vomiting and/or Nausea with Abdominal Pain
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 79 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 57 of this family's pathways, 377 estate-wide; 4460 PC severe illness assessment capability — 55 of this family's pathways, 130 estate-wide; 4019 AMB toxic ingestion — 43 of this family's pathways, 55 estate-wide; 4002 AMB meningitis — 37 of this family's pathways, 140 estate-wide; 4000 AMB septicaemia — 33 of this family's pathways, 158 estate-wide; 4017 AMB gastrointestinal bleed — 32 of this family's pathways, 82 estate-wide; 4060 AMB acute abdomen — 29 of this family's pathways, 74 estate-wide
- **Most common SNOMED concepts:** 103001002 Feeling feverish — 65 of this family's pathways, 322 estate-wide; 130987000 Acute confusion — 56 of this family's pathways, 185 estate-wide; 161941007 Dyspnoea at rest — 49 of this family's pathways, 131 estate-wide; 213257006 Generally unwell — 48 of this family's pathways, 142 estate-wide; 267036007 Dyspnoea — 47 of this family's pathways, 223 estate-wide; 707857003 Exposure to Ebola virus — 43 of this family's pathways, 60 estate-wide; 80593000 Ingestion of foreign material — 42 of this family's pathways, 57 estate-wide; 269899009 Faeces colour: tarry — 39 of this family's pathways, 75 estate-wide
- **Strongest overlaps:** HA_C02 (shared SNOMED concepts, Jaccard 0.41); HA_C04_01 (shared SNOMED concepts, Jaccard 0.41); HA_C05 (shared symptom discriminators, Jaccard 0.36)
- **Major boundary pathways:** PW1829 Critical Illness Assessment  (cross-family hub, 17 external links); PT6 Non-emergency Ambulance Closure (cross-family hub, 11 external links); PW936 Vomiting and/or Nausea (cross-family hub, 10 external links); PW939 Vomiting and/or Nausea (cross-family hub, 10 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C02 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
5. This is one of the larger families. Does it contain more than one clinical area that should be separated?

---

## HA_C04_01 — Family_03

**81 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Abdominal or Flank Injury, Blunt | Face, Neck Pain or Swelling | Dizziness or Vertigo
- **Dominant clinical areas:** head | urinary | face
- **Representative pathways:** PW1401 Head, Facial or Neck Injury, Blunt; PW1397 Eye Injury, Blunt; PW662 Eye Injury, Blunt; PW686 Head, Facial or Neck Injury, Blunt; PW1713 Nosebleeds after Injury; PW1730 Nosebleeds after Injury
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 55 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 51 of this family's pathways, 377 estate-wide; 4033 AMB new/worsening breathlessness — 28 of this family's pathways, 123 estate-wide; 4010 ALL assault, sexual — 26 of this family's pathways, 160 estate-wide; 4043 AMB major head/neck injury — 16 of this family's pathways, 18 estate-wide; 4134 ED full ophthalmic ED assessment and management capability — 16 of this family's pathways, 40 estate-wide; 4028 AMB stroke — 15 of this family's pathways, 31 estate-wide; 4091 AMB Head injury, full ED assessment required — 15 of this family's pathways, 18 estate-wide
- **Most common SNOMED concepts:** 267036007 Dyspnoea — 35 of this family's pathways, 223 estate-wide; 103001002 Feeling feverish — 31 of this family's pathways, 322 estate-wide; 422608009 Sexual assault — 26 of this family's pathways, 160 estate-wide; 90774003 Victim of physical assault — 25 of this family's pathways, 125 estate-wide; 130987000 Acute confusion — 24 of this family's pathways, 185 estate-wide; 95667004 Unilateral facial paresis — 23 of this family's pathways, 70 estate-wide; 29164008 Disturbance in speech — 21 of this family's pathways, 56 estate-wide; 213257006 Generally unwell — 17 of this family's pathways, 142 estate-wide
- **Strongest overlaps:** HA_C05 (shared SNOMED concepts, Jaccard 0.42); HA_C03 (shared SNOMED concepts, Jaccard 0.41); HA_C02 (shared SNOMED concepts, Jaccard 0.40)
- **Major boundary pathways:** PW1858 Emergency or Urgent Treament Centre, Self-triage (cross-family hub, 24 external links); PW692 Head, Facial or Neck Injury, Penetrating (cross-family hub, 9 external links); PW1030 Palpitations (cross-family hub, 7 external links); PW1028 Palpitations (cross-family hub, 3 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C05 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
5. This is one of the larger families. Does it contain more than one clinical area that should be separated?

---

## HA_C05 — Family_04

**70 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Coughing up Blood | Earache | Vaginal Bleeding
- **Dominant clinical areas:** genital | not area specific | ear
- **Representative pathways:** PW1321 Foreign Body, Rectum; PW1322 Foreign Body, Vaginal; PW1531 Foreign Body, Rectum; PW654 Earache; PW1010 Genital Injury, Penetrating; PW656 Earache
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 55 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 36 of this family's pathways, 377 estate-wide; 4010 ALL assault, sexual — 20 of this family's pathways, 160 estate-wide; 4460 PC severe illness assessment capability — 20 of this family's pathways, 130 estate-wide; 4060 AMB acute abdomen — 19 of this family's pathways, 74 estate-wide; 4002 AMB meningitis — 16 of this family's pathways, 140 estate-wide; 4000 AMB septicaemia — 15 of this family's pathways, 158 estate-wide; 4087 AMB cord prolapse — 15 of this family's pathways, 16 estate-wide
- **Most common SNOMED concepts:** 103001002 Feeling feverish — 31 of this family's pathways, 322 estate-wide; 130987000 Acute confusion — 25 of this family's pathways, 185 estate-wide; 422608009 Sexual assault — 20 of this family's pathways, 160 estate-wide; 267036007 Dyspnoea — 19 of this family's pathways, 223 estate-wide; 275723000 Patient's condition deteriorating — 19 of this family's pathways, 216 estate-wide; 289530006 Vaginal bleeding — 17 of this family's pathways, 22 estate-wide; 161882006 Stiff neck — 16 of this family's pathways, 139 estate-wide; 409668002 Photophobia — 16 of this family's pathways, 142 estate-wide
- **Strongest overlaps:** HA_C04_01 (shared SNOMED concepts, Jaccard 0.42); HA_C02 (shared SNOMED concepts, Jaccard 0.42); HA_C03 (shared symptom discriminators, Jaccard 0.36)
- **Major boundary pathways:** PW1010 Genital Injury, Penetrating (cross-family hub, 5 external links); PA218 Choking on liquids now, infants (cross-family hub, 5 external links); PT2 Emergency Ambulance Closure (strong boundary pathway, 172 external links); PT1 Emergency Ambulance Closure (strong boundary pathway, 111 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C04_01 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
5. This is one of the larger families. Does it contain more than one clinical area that should be separated?

---

## HA_C06 — Family_05

**55 pathways.** Named from: neutral. Structural cohesion: high (graph and clinical-feature evidence agree).

- **Dominant symptom groups:** Breathing Problems, Breathlessness or Wheeze | Cough | Skin, Rash
- **Dominant clinical areas:** chest | not area specific | nose
- **Representative pathways:** PW1050 Sinusitis (Declared); PW762 Cough; PW978 Cough; PW979 Cough; PW1040 Cold or Flu Symptoms; PW1041 Cold or Flu Symptoms
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 48 of this family's pathways, 514 estate-wide; 4000 AMB septicaemia — 24 of this family's pathways, 158 estate-wide; 4002 AMB meningitis — 23 of this family's pathways, 140 estate-wide; 4052 ED full ED assessment and management capability — 23 of this family's pathways, 377 estate-wide; 4460 PC severe illness assessment capability — 21 of this family's pathways, 130 estate-wide; 4020 PC assessment and management capability, minor condition — 14 of this family's pathways, 43 estate-wide; 4459 AMB critical illness assessment — 11 of this family's pathways, 48 estate-wide; 4033 AMB new/worsening breathlessness — 7 of this family's pathways, 123 estate-wide
- **Most common SNOMED concepts:** 275723000 Patient's condition deteriorating — 32 of this family's pathways, 216 estate-wide; 103001002 Feeling feverish — 31 of this family's pathways, 322 estate-wide; 130987000 Acute confusion — 26 of this family's pathways, 185 estate-wide; 267036007 Dyspnoea — 24 of this family's pathways, 223 estate-wide; 423902002 Purpura — 24 of this family's pathways, 184 estate-wide; 161882006 Stiff neck — 23 of this family's pathways, 139 estate-wide; 409668002 Photophobia — 23 of this family's pathways, 142 estate-wide; 161941007 Dyspnoea at rest — 18 of this family's pathways, 131 estate-wide
- **Strongest overlaps:** HA_C02 (shared SNOMED concepts, Jaccard 0.44); HA_C04_01 (shared SNOMED concepts, Jaccard 0.38); HA_C03 (shared SNOMED concepts, Jaccard 0.35)
- **Major boundary pathways:** PA94 Allergic Reaction (cross-family hub, 16 external links); PW560 Breathing Problems, Breathlessness or Wheeze (cross-family hub, 11 external links); PW559 Breathing Problems, Breathlessness or Wheeze (cross-family hub, 10 external links); PW556 Breathing Problems, Breathlessness or Wheeze (cross-family hub, 10 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C02 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C01_00 — Family_06

**54 pathways.** Named from: neutral. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** Immediate threats to life | Electrical Injury    | Major Trauma
- **Dominant clinical areas:** back | chest | abdomen
- **Representative pathways:** PA136 Immediate threats to life, SPA/OOH version, 3rd party; PA144 Immediate threats to life, SPA/OOH version; PA152 Immediate threats to life, SPA/OOH version; PA156 Immediate threats to life, SPA/OOH version; PA135 Immediate threats to life, Ambulance version, 3rd party; PA143 Immediate threats to life, Ambulance version
- **Most common symptom discriminators:** 4216 AMB major blood loss, non-trauma — 24 of this family's pathways, 24 estate-wide; 4217 AMB major blood loss, non-trauma AND respiratory distress — 24 of this family's pathways, 24 estate-wide; 4218 AMB major blood loss, non-trauma AND shock — 24 of this family's pathways, 24 estate-wide; 4219 AMB major blood loss, non-trauma AND septicaemia — 24 of this family's pathways, 24 estate-wide; 4221 AMB threat to life, environmental — 24 of this family's pathways, 26 estate-wide; 4215 AMB major blood loss, trauma — 23 of this family's pathways, 27 estate-wide; 4220 AMB major blood loss, trauma AND amputated digits — 23 of this family's pathways, 23 estate-wide; 4048 AMB fit/convulsion — 21 of this family's pathways, 42 estate-wide
- **Most common SNOMED concepts:** 275723000 Patient's condition deteriorating — 24 of this family's pathways, 216 estate-wide; 39104002 Illness — 24 of this family's pathways, 35 estate-wide; 423902002 Purpura — 24 of this family's pathways, 184 estate-wide; 161941007 Dyspnoea at rest — 21 of this family's pathways, 131 estate-wide; 102874004 Possible pregnancy — 12 of this family's pathways, 98 estate-wide; 422608009 Sexual assault — 11 of this family's pathways, 160 estate-wide; 90774003 Victim of physical assault — 9 of this family's pathways, 125 estate-wide; 118216002 Labour finding — 8 of this family's pathways, 17 estate-wide
- **Strongest overlaps:** HA_C01_01 (shared SNOMED concepts, Jaccard 0.36); HA_C04_00 (shared SNOMED concepts, Jaccard 0.33); HA_C00 (shared SNOMED concepts, Jaccard 0.30)
- **Major boundary pathways:** PA162 Frequent Caller (cross-family hub, 26 external links); PA110 Social & information SPA/OOH Version (cross-family hub, 14 external links); PA112 Immediate threats to life, SPA/OOH version, 3rd party (cross-family hub, 13 external links); PA128 Immediate threats to life, SPA/OOH version, 3rd party (cross-family hub, 13 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C01_01 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C08 — Family_07

**33 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PP100 Entry pathway, adult (Ambulance setting); PP101 Entry pathway, adult (OOH & SPA setting); PP102 Entry pathway, child (Ambulance setting); PP103 Entry pathway, child (OOH & SPA setting); PP104 Entry pathway, toddler (Ambulance setting); PP105 Entry pathway, toddler (OOH & SPA setting)
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** 39104002 Illness — 8 of this family's pathways, 35 estate-wide; 275723000 Patient's condition deteriorating — 8 of this family's pathways, 216 estate-wide; 423902002 Purpura — 8 of this family's pathways, 184 estate-wide; 103001002 Feeling feverish — 4 of this family's pathways, 322 estate-wide; 10000006 Radiating chest pain — 2 of this family's pathways, 7 estate-wide; 59139008 Crushing chest pain — 2 of this family's pathways, 7 estate-wide
- **Strongest overlaps:** HA_C01_00 (shared SNOMED concepts, Jaccard 0.12); HA_C07_00 (shared SNOMED concepts, Jaccard 0.08); HA_C09 (shared SNOMED concepts, Jaccard 0.07)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?

---

## HA_C07_00 — Family_08

**32 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Non-trauma Emergency | Chest and Upper Back Pain  | Fits Within the Last 12 Hours   
- **Dominant clinical areas:** back | chest | not area specific
- **Representative pathways:** PA114 Non-trauma emergency, 3rd party; PA122 Non-trauma emergency, 3rd Party; PA130 Non-trauma emergency, 3rd Party; PA138 Non-trauma emergency, 3rd Party; PA146 Non-trauma emergency; PA150 Non-trauma emergency
- **Most common symptom discriminators:** 4000 AMB septicaemia — 28 of this family's pathways, 158 estate-wide; 4106 AMB shock — 25 of this family's pathways, 53 estate-wide; 4003 PC full Primary Care assessment and prescribing capability — 20 of this family's pathways, 514 estate-wide; 4002 AMB meningitis — 17 of this family's pathways, 140 estate-wide; 4044 AMB suicide attempt — 12 of this family's pathways, 29 estate-wide; 4102 AMB respiratory distress — 12 of this family's pathways, 39 estate-wide; 4212 AMB cardiac arrest — 12 of this family's pathways, 34 estate-wide; 4460 PC severe illness assessment capability — 12 of this family's pathways, 130 estate-wide
- **Most common SNOMED concepts:** 275723000 Patient's condition deteriorating — 27 of this family's pathways, 216 estate-wide; 423902002 Purpura — 26 of this family's pathways, 184 estate-wide; 161445009 H/O: diabetes mellitus — 20 of this family's pathways, 76 estate-wide; 161882006 Stiff neck — 16 of this family's pathways, 139 estate-wide; 409668002 Photophobia — 16 of this family's pathways, 142 estate-wide; 103001002 Feeling feverish — 14 of this family's pathways, 322 estate-wide; 130987000 Acute confusion — 10 of this family's pathways, 185 estate-wide; 102874004 Possible pregnancy — 8 of this family's pathways, 98 estate-wide
- **Strongest overlaps:** HA_C02 (shared SNOMED concepts, Jaccard 0.33); HA_C09 (shared SNOMED concepts, Jaccard 0.32); HA_C06 (shared SNOMED concepts, Jaccard 0.26)
- **Major boundary pathways:** PA21 Chest and Upper Back Pain (cross-family hub, 19 external links); PA114 Non-trauma emergency, 3rd party (cross-family hub, 8 external links); PA122 Non-trauma emergency, 3rd Party (cross-family hub, 8 external links); PA130 Non-trauma emergency, 3rd Party (cross-family hub, 8 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C02 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C10 — head

**28 pathways.** Named from: dominant area group (50% of the family's pathways). Structural cohesion: high (graph and clinical-feature evidence agree).

- **Dominant symptom groups:** Toothache Without Dental Injury | Dental Problems | Face, Neck Pain or Swelling
- **Dominant clinical areas:** mouth | head | face
- **Representative pathways:** PT225 Dental Analgesia Assessment; PW1714 Teething; PW1517 Other Dental Problems; PT517 Dental Analgesia Assessment; PT518 Dental Analgesia Assessment; PW1607 Breast Problems
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 21 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 15 of this family's pathways, 377 estate-wide; 4047 PC full dental assessment and prescribing capability — 9 of this family's pathways, 14 estate-wide; 4000 AMB septicaemia — 5 of this family's pathways, 158 estate-wide; 4002 AMB meningitis — 5 of this family's pathways, 140 estate-wide; 4022 ED foreign body, removal required — 5 of this family's pathways, 31 estate-wide; 4010 ALL assault, sexual — 4 of this family's pathways, 160 estate-wide; 4392 PC dental brace problem — 4 of this family's pathways, 4 estate-wide
- **Most common SNOMED concepts:** 103001002 Feeling feverish — 13 of this family's pathways, 322 estate-wide; 267036007 Dyspnoea — 6 of this family's pathways, 223 estate-wide; 128482007 Acute inflammatory disease — 5 of this family's pathways, 57 estate-wide; 130987000 Acute confusion — 5 of this family's pathways, 185 estate-wide; 161882006 Stiff neck — 5 of this family's pathways, 139 estate-wide; 213257006 Generally unwell — 5 of this family's pathways, 142 estate-wide; 247441003 Erythema — 5 of this family's pathways, 60 estate-wide; 275723000 Patient's condition deteriorating — 5 of this family's pathways, 216 estate-wide
- **Strongest overlaps:** HA_C06 (shared SNOMED concepts, Jaccard 0.32); HA_C02 (shared SNOMED concepts, Jaccard 0.28); HA_C04_01 (shared SNOMED concepts, Jaccard 0.27)
- **Major boundary pathways:** PW1515 Dental Bleeding (strong boundary pathway, 4 external links); PW870 Toothache without Dental Injury (strong boundary pathway, 4 external links); PW1048 Sinusitis (Declared) (strong boundary pathway, 3 external links); PW1548 Face, Neck Pain or Swelling (strong boundary pathway, 3 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `head` the right name?
3. It overlaps strongly with HA_C06 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C01_03 — Family_10

**27 pathways.** Named from: neutral. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PW1811 Clinical Hub Closure; PW1821 Clinical Hub Closure - Mental Health; PW1849 PaCCS Home Management Suite; PW1846 PaCCS Service Search; PW1848 PaCCS Ambulance Dispatch; PW888 DEVELOPMENT test pathway only
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 4 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 3 of this family's pathways, 377 estate-wide; 4048 AMB fit/convulsion — 2 of this family's pathways, 42 estate-wide; 4212 AMB cardiac arrest — 2 of this family's pathways, 34 estate-wide; 4214 AMB unconscious — 2 of this family's pathways, 20 estate-wide; 4301 AMB major blood loss — 2 of this family's pathways, 27 estate-wide; 4419 ED mental health crisis — 2 of this family's pathways, 3 estate-wide; 4456 PC full mental health assessment capability — 2 of this family's pathways, 8 estate-wide
- **Most common SNOMED concepts:** 813381000000102 Foreign body associated with wound — 12 of this family's pathways, 72 estate-wide; 161445009 H/O: diabetes mellitus — 1 of this family's pathways, 76 estate-wide; 248110007 Sexual assault — 1 of this family's pathways, 13 estate-wide; 161480008 H/O: epilepsy — 1 of this family's pathways, 11 estate-wide; 422608009 Sexual assault — 1 of this family's pathways, 160 estate-wide; 52684005 Assault — 1 of this family's pathways, 13 estate-wide; 82313006 Suicide attempt — 1 of this family's pathways, 13 estate-wide; 90774003 Victim of physical assault — 1 of this family's pathways, 125 estate-wide
- **Strongest overlaps:** HA_C09 (shared symptom discriminators, Jaccard 0.27); HA_C01_00 (shared symptom discriminators, Jaccard 0.26); HA_C01_01 (shared SNOMED concepts, Jaccard 0.19)
- **Major boundary pathways:** PT510 Emergency CPR Pathway (cross-family hub, 18 external links); PA25 Major Bleeding, 1st & 3rd Party (strong boundary pathway, 36 external links); PT504 Unconsciousness, Closure (strong boundary pathway, 17 external links); PA13 Environmental Threat 3rd Party (strong boundary pathway, 17 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C09 — not area specific

**26 pathways.** Named from: dominant clinical area (50% of the family's pathways). Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Tiredness (Fatigue) | Sleep Difficulties | Alcohol Intoxication
- **Dominant clinical areas:** not area specific | head
- **Representative pathways:** PW1070 Tiredness (Fatigue); PW1071 Tiredness (Fatigue); PW1073 Tiredness (Fatigue); PW1686 Sleep Difficulties; PW1697 Sleep Difficulties; PW1074 Tiredness (Fatigue), Pregnant
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 16 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 11 of this family's pathways, 377 estate-wide; 4180 PC mental health assessment, alcohol misuse — 11 of this family's pathways, 13 estate-wide; 4181 PC mental health assessment, drug misuse — 11 of this family's pathways, 12 estate-wide; 4177 PC depressed mood — 10 of this family's pathways, 14 estate-wide; 4179 PC anxiety/panic — 10 of this family's pathways, 14 estate-wide; 4244 AMB suicidal, means and plan — 6 of this family's pathways, 10 estate-wide; 4001 AMB acute coronary syndrome — 5 of this family's pathways, 49 estate-wide
- **Most common SNOMED concepts:** 130987000 Acute confusion — 9 of this family's pathways, 185 estate-wide; 24199005 Feeling agitated — 9 of this family's pathways, 13 estate-wide; 307077003 Feeling hopeless — 9 of this family's pathways, 13 estate-wide; 366979004 Depressed mood — 9 of this family's pathways, 13 estate-wide; 417523004 Loss of interest in previously enjoyable activity — 9 of this family's pathways, 13 estate-wide; 48694002 Anxiety — 9 of this family's pathways, 13 estate-wide; 182877009 Drug dosage altered — 7 of this family's pathways, 99 estate-wide; 266712008 New medication commenced — 7 of this family's pathways, 105 estate-wide
- **Strongest overlaps:** HA_C07_00 (shared SNOMED concepts, Jaccard 0.32); HA_C01_03 (shared symptom discriminators, Jaccard 0.27); HA_C11 (shared SNOMED concepts, Jaccard 0.26)
- **Major boundary pathways:** PN5128 Assessment of Required Level of Response (strong boundary pathway, 24 external links); PT8 Mental Health Safety Closure (strong boundary pathway, 7 external links); PW1823 Cold Exposure (strong boundary pathway, 6 external links); PW1749 Behaviour Change (strong boundary pathway, 5 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `not area specific` the right name?
3. It overlaps strongly with HA_C07_00 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C04_00 — Lower Back Injury, Blunt

**16 pathways.** Named from: dominant symptom group (50% of the family's pathways). Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Lower Back Injury, Blunt | Nosebleeds without injury | Rectal Pain, Swelling, Lump or Itch
- **Dominant clinical areas:** back | nose | genital
- **Representative pathways:** PW1320 Foreign Body, Penis; PW1406 Genital Injury, Blunt; PW833 Genital Injury, Blunt; PW1420 Lower Back Injury, Blunt; PW795 Lower Back Injury, Blunt; PW1596 Lower Back Injury, Blunt
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 16 of this family's pathways, 514 estate-wide; 4052 ED full ED assessment and management capability — 16 of this family's pathways, 377 estate-wide; 4010 ALL assault, sexual — 13 of this family's pathways, 160 estate-wide; 4017 AMB gastrointestinal bleed — 8 of this family's pathways, 82 estate-wide; 4033 AMB new/worsening breathlessness — 8 of this family's pathways, 123 estate-wide; 4008 AMB motor and/or sensory deficit — 4 of this family's pathways, 17 estate-wide; 4018 AMB severe pain — 4 of this family's pathways, 45 estate-wide; 4060 AMB acute abdomen — 4 of this family's pathways, 74 estate-wide
- **Most common SNOMED concepts:** 422608009 Sexual assault — 13 of this family's pathways, 160 estate-wide; 90774003 Victim of physical assault — 10 of this family's pathways, 125 estate-wide; 267036007 Dyspnoea — 9 of this family's pathways, 223 estate-wide; 267051003 Vomiting blood - fresh — 8 of this family's pathways, 71 estate-wide; 40835002 Coffee ground vomiting — 8 of this family's pathways, 71 estate-wide; 161647008 H/O: anticoagulant therapy — 7 of this family's pathways, 125 estate-wide; 262519004 Multiple injuries — 7 of this family's pathways, 68 estate-wide; 64779008 Blood coagulation disorder — 7 of this family's pathways, 106 estate-wide
- **Strongest overlaps:** HA_C01_00 (shared SNOMED concepts, Jaccard 0.33); HA_C02 (shared SNOMED concepts, Jaccard 0.26); HA_C10 (shared SNOMED concepts, Jaccard 0.24)
- **Major boundary pathways:** PW1596 Lower Back Injury, Blunt (strong boundary pathway, 4 external links); PW790 Lower Back Injury, Blunt (strong boundary pathway, 4 external links); PW1597 Lower Back Injury, Blunt (strong boundary pathway, 3 external links); PW793 Lower Back Injury, Blunt (strong boundary pathway, 3 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Lower Back Injury, Blunt` the right name?
3. It overlaps strongly with HA_C01_00 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C11 — Family_13

**15 pathways.** Named from: neutral. Structural cohesion: high (graph and clinical-feature evidence agree).

- **Dominant symptom groups:** Eye or Eyelid Problems | Eye, Visual Loss or Disturbance | Eye, Red or Irritable
- **Dominant clinical areas:** eye
- **Representative pathways:** PW1134 Eye, Red or Irritable; PW1146 Eye, Sticky, Watery; PW1128 Eye, Painful; PW1137 Eye, Red or Irritable; PW1126 Eye, Painful; PW1124 Eye, Visual Loss or Disturbance
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 11 of this family's pathways, 514 estate-wide; 4310 PC extended ophthalmic assessment and prescribing capability (MECS) — 10 of this family's pathways, 18 estate-wide; 4311 PC extended ophthalmic assessment and management capability, minor condition (MECS) — 8 of this family's pathways, 11 estate-wide; 4312 ED extended ophthalmic assessment and prescribing capability (MECS) — 8 of this family's pathways, 17 estate-wide; 4052 ED full ED assessment and management capability — 6 of this family's pathways, 377 estate-wide; 4002 AMB meningitis — 4 of this family's pathways, 140 estate-wide; 4020 PC assessment and management capability, minor condition — 4 of this family's pathways, 43 estate-wide; 4000 AMB septicaemia — 3 of this family's pathways, 158 estate-wide
- **Most common SNOMED concepts:** 272032002 C/O - watering eyes — 9 of this family's pathways, 14 estate-wide; 41652007 Pain in eye — 9 of this family's pathways, 31 estate-wide; 63102001 Visual disturbance — 9 of this family's pathways, 53 estate-wide; 246679005 Discharge from eye — 8 of this family's pathways, 11 estate-wide; 314496008 Contact lens related disorder — 8 of this family's pathways, 13 estate-wide; 103001002 Feeling feverish — 6 of this family's pathways, 322 estate-wide; 409668002 Photophobia — 6 of this family's pathways, 142 estate-wide; 78598000 Superficial injury of eye — 6 of this family's pathways, 11 estate-wide
- **Strongest overlaps:** HA_C05 (shared SNOMED concepts, Jaccard 0.31); HA_C04_01 (shared SNOMED concepts, Jaccard 0.28); HA_C09 (shared SNOMED concepts, Jaccard 0.26)
- **Major boundary pathways:** PW1621 Skin, Yellow (strong boundary pathway, 5 external links); PW1122 Eye, Visual Loss or Disturbance (strong boundary pathway, 4 external links); PW1124 Eye, Visual Loss or Disturbance (strong boundary pathway, 4 external links); PW1137 Eye, Red or Irritable (strong boundary pathway, 3 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C05 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C01_01 — Trauma Emergency

**12 pathways.** Named from: dominant symptom group (100% of the family's pathways). Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** Trauma Emergency
- **Dominant clinical areas:** —
- **Representative pathways:** PA137 Trauma emergency, 3rd Party; PA141 Trauma emergency, 1st Party; PA121 Trauma emergency, 3rd Party; PA125 Trauma emergency, 1st Party; PA129 Trauma emergency, 3rd Party; PA133 Trauma emergency, 1st Party
- **Most common symptom discriminators:** 4102 AMB respiratory distress — 12 of this family's pathways, 39 estate-wide; 4106 AMB shock — 12 of this family's pathways, 53 estate-wide; 4129 PC minor injury — 12 of this family's pathways, 32 estate-wide; 4135 AMB fall, significant — 12 of this family's pathways, 17 estate-wide; 4153 AMB bleeding, significant — 12 of this family's pathways, 25 estate-wide; 4191 AMB trapped — 12 of this family's pathways, 15 estate-wide; 4222 AMB major trauma AND significant blood loss — 12 of this family's pathways, 12 estate-wide; 4224 AMB gunshot OR stab injury, head/neck — 12 of this family's pathways, 12 estate-wide
- **Most common SNOMED concepts:** 813381000000102 Foreign body associated with wound — 12 of this family's pathways, 72 estate-wide; 161941007 Dyspnoea at rest — 10 of this family's pathways, 131 estate-wide; 248110007 Sexual assault — 8 of this family's pathways, 13 estate-wide; 267036007 Dyspnoea — 8 of this family's pathways, 223 estate-wide; 29164008 Disturbance in speech — 8 of this family's pathways, 56 estate-wide; 52684005 Assault — 8 of this family's pathways, 13 estate-wide; 713512009 Muscle weakness of upper limb — 8 of this family's pathways, 51 estate-wide; 80313002 Palpitations — 8 of this family's pathways, 29 estate-wide
- **Strongest overlaps:** HA_C01_00 (shared SNOMED concepts, Jaccard 0.36); HA_C07_00 (shared SNOMED concepts, Jaccard 0.21); HA_C09 (shared SNOMED concepts, Jaccard 0.21)
- **Major boundary pathways:** PA113 Trauma emergency, 3rd party (cross-family hub, 13 external links); PA121 Trauma emergency, 3rd Party (cross-family hub, 13 external links); PA129 Trauma emergency, 3rd Party (cross-family hub, 13 external links); PA137 Trauma emergency, 3rd Party (cross-family hub, 13 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Trauma Emergency` the right name?
3. It overlaps strongly with HA_C01_00 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C01_02 — Entry pathway

**11 pathways.** Named from: dominant symptom group (100% of the family's pathways). Structural cohesion: low (pathways mostly transfer outside the family).

- **Dominant symptom groups:** Entry pathway
- **Dominant clinical areas:** —
- **Representative pathways:** PFA1 Calling About Self; PFA3 Calling About Someone Else; PFC1 Calling About Self; PFC3 Calling About Someone Else; PFT Calling About Someone Else; PHCP Calling About Someone Else
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C08 (shared questions, Jaccard 0.04); HA_C01_00 (shared questions, Jaccard 0.04); HA_C05 (shared questions, Jaccard 0.03)
- **Major boundary pathways:** PFA3 Calling About Someone Else (strong boundary pathway, 5 external links); PFC3 Calling About Someone Else (strong boundary pathway, 5 external links); PMA3 Calling About Someone Else (strong boundary pathway, 5 external links); PMC3 Calling About Someone Else (strong boundary pathway, 5 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Entry pathway` the right name?
3. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C07_01 — Family_16

**8 pathways.** Named from: neutral. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PA18 Fighting for Breath 1st Party ; PA41 Fighting for Breath 3rd Party; PA55 Fighting for Breath 3rd Party; PA6 Fighting for Breath 3rd Party; PA71 Fighting for Breath 1st Party ; PA93 Recovery From Successful Cardio-Pulmonary Resuscitation
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** 161514008 H/O: aortic aneurysm — 2 of this family's pathways, 4 estate-wide; 19346006 Marfan's syndrome — 2 of this family's pathways, 8 estate-wide
- **Strongest overlaps:** HA_C07_00 (shared questions, Jaccard 0.05); HA_C14 (shared questions, Jaccard 0.04); HA_C01_03 (shared questions, Jaccard 0.03)
- **Major boundary pathways:** PT506 Emergency Tracheostomy or Laryngectomy (strong boundary pathway, 16 external links); PA93 Recovery From Successful Cardio-Pulmonary Resuscitation (strong boundary pathway, 8 external links); PT418 Diabetic Hypoglycaemic Closure (strong boundary pathway, 6 external links); PA41 Fighting for Breath 3rd Party (strong boundary pathway, 4 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?

---

## HA_C12 — Ambulance Dispatch

**6 pathways.** Named from: dominant symptom group (100% of the family's pathways). Structural cohesion: high (graph and clinical-feature evidence agree).

- **Dominant symptom groups:** Ambulance Dispatch
- **Dominant clinical areas:** —
- **Representative pathways:** PW1813 Ambulance Dispatch; PW1814 Ambulance Dispatch; PW1815 Ambulance Dispatch; PW1816 Ambulance Dispatch; PW1817 Ambulance Dispatch; PW1818 Ambulance Dispatch Closure
- **Most common symptom discriminators:** 4106 AMB shock — 6 of this family's pathways, 53 estate-wide; 4301 AMB major blood loss — 6 of this family's pathways, 27 estate-wide; 4000 AMB septicaemia — 5 of this family's pathways, 158 estate-wide; 4101 AMB anaphylaxis — 5 of this family's pathways, 22 estate-wide; 4102 AMB respiratory distress — 5 of this family's pathways, 39 estate-wide; 4016 AMB aortic aneurysm, rupture/dissection — 4 of this family's pathways, 10 estate-wide; 4001 AMB acute coronary syndrome — 2 of this family's pathways, 49 estate-wide; 4028 AMB stroke — 2 of this family's pathways, 31 estate-wide
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C11 (shared symptom discriminators, Jaccard 0.16); HA_C07_00 (shared symptom discriminators, Jaccard 0.12); HA_C01_00 (shared symptom discriminators, Jaccard 0.11)
- **Major boundary pathways:** PW1818 Ambulance Dispatch Closure (weak boundary pathway, 2 external links); PW1814 Ambulance Dispatch (weak boundary pathway, 1 external links); PW1815 Ambulance Dispatch (weak boundary pathway, 1 external links)

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Ambulance Dispatch` the right name?
3. Are the boundary pathways listed above clinically part of this family, of another, or genuinely shared?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C13 — Family_18

**2 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT230 Assistance needed at home due to inability to get off the floor, Emergency Closure, Non Trauma; PT3 Assistance needed at home due to inability to get off the floor, Closure
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C16 (shared questions, Jaccard 1.00); HA_C17 (shared questions, Jaccard 1.00); HA_C20 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C16 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C14 — Family_19

**2 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT318 Non-emergency Ambulance Closure, Breathlessness; PT503 Emergency Ambulance Closure, Non-Trauma, Breathlessness
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C13 (shared questions, Jaccard 0.80); HA_C16 (shared questions, Jaccard 0.80); HA_C17 (shared questions, Jaccard 0.80)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C13 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C16 — Family_20

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT17 Ambulance due to Clinical Reasons
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C13 (shared questions, Jaccard 1.00); HA_C17 (shared questions, Jaccard 1.00); HA_C20 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C13 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C17 — Family_21

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT18 Ambulance due to Transportation Reasons
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C13 (shared questions, Jaccard 1.00); HA_C16 (shared questions, Jaccard 1.00); HA_C20 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C13 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C18 — Family_22

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT19 Emergency Ambulance due to Clinical Reasons
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C19 (shared questions, Jaccard 1.00); HA_C21 (shared questions, Jaccard 1.00); HA_C22 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C19 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C19 — Family_23

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT229 Emergency Ambulance Closure, Override
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C18 (shared questions, Jaccard 1.00); HA_C21 (shared questions, Jaccard 1.00); HA_C22 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C18 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C20 — Family_24

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT321 Non-emergency Ambulance Closure, Override
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C13 (shared questions, Jaccard 1.00); HA_C16 (shared questions, Jaccard 1.00); HA_C17 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C13 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C21 — Family_25

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT40 Emergency Ambulance Closure, Non Trauma
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C18 (shared questions, Jaccard 1.00); HA_C19 (shared questions, Jaccard 1.00); HA_C22 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C18 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C22 — Family_26

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT405 Emergency Ambulance Closure, Wound Bleeding, Neck, Torso
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C18 (shared questions, Jaccard 1.00); HA_C19 (shared questions, Jaccard 1.00); HA_C21 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C18 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C23 — Family_27

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT417 Emergency Ambulance Closure, Vaginal Bleeding in Pregnancy
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C18 (shared questions, Jaccard 1.00); HA_C19 (shared questions, Jaccard 1.00); HA_C21 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C18 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C24 — Family_28

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT508 Emergency Ambulance (Override) Closure
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C18 (shared questions, Jaccard 1.00); HA_C19 (shared questions, Jaccard 1.00); HA_C21 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C18 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C25 — Family_29

**1 pathways.** Named from: neutral. Structural cohesion: moderate (one of graph or clinical-feature evidence is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** PT509 Non-Emergency Ambulance (Override) Closure
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C13 (shared questions, Jaccard 1.00); HA_C16 (shared questions, Jaccard 1.00); HA_C17 (shared questions, Jaccard 1.00)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C13 (driver: shared questions). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C38 — Repeat Prescription (HA_C38)

**1 pathways.** Named from: dominant symptom group (100% of the family's pathways); family id appended because another family shares the same dominant value. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** Repeat Prescription
- **Dominant clinical areas:** —
- **Representative pathways:** PW1808 Prescription Request 
- **Most common symptom discriminators:** 4003 PC full Primary Care assessment and prescribing capability — 1 of this family's pathways, 514 estate-wide; 4413 PC repeat prescription — 1 of this family's pathways, 7 estate-wide; 4452 PC symptomatic assessment — 1 of this family's pathways, 3 estate-wide
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C41 (shared symptom discriminators, Jaccard 0.33); HA_C04_00 (shared symptom discriminators, Jaccard 0.06); HA_C11 (shared symptom discriminators, Jaccard 0.05)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Repeat Prescription (HA_C38)` the right name?
3. It overlaps strongly with HA_C41 (driver: shared symptom discriminators). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C41 — Repeat Prescription (HA_C41)

**1 pathways.** Named from: dominant symptom group (100% of the family's pathways); family id appended because another family shares the same dominant value. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** Repeat Prescription
- **Dominant clinical areas:** —
- **Representative pathways:** PW1827 Emergency Prescription 111 online
- **Most common symptom discriminators:** 4413 PC repeat prescription — 1 of this family's pathways, 7 estate-wide
- **Most common SNOMED concepts:** —
- **Strongest overlaps:** HA_C38 (shared symptom discriminators, Jaccard 0.33); HA_C01_00 (shared symptom discriminators, Jaccard 0.01); HA_C01_03 (shared symptom discriminators, Jaccard 0.01)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. We have named it from its dominant metadata. Is `Repeat Prescription (HA_C41)` the right name?
3. It overlaps strongly with HA_C38 (driver: shared symptom discriminators). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C48 — Family_32

**1 pathways.** Named from: neutral. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** SP1 Assessing Safety 1st Party 
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** 707857003 Exposure to Ebola virus — 1 of this family's pathways, 60 estate-wide
- **Strongest overlaps:** HA_C49 (shared SNOMED concepts, Jaccard 1.00); HA_C01_03 (shared questions, Jaccard 0.01); HA_C06 (shared questions, Jaccard 0.01)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C49 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## HA_C49 — Family_33

**1 pathways.** Named from: neutral. Structural cohesion: low (neither graph nor clinical-feature cohesion is strong).

- **Dominant symptom groups:** —
- **Dominant clinical areas:** —
- **Representative pathways:** SP3 Assessing Safety 3rd Party
- **Most common symptom discriminators:** —
- **Most common SNOMED concepts:** 707857003 Exposure to Ebola virus — 1 of this family's pathways, 60 estate-wide
- **Strongest overlaps:** HA_C48 (shared SNOMED concepts, Jaccard 1.00); HA_C14 (shared questions, Jaccard 0.03); HA_C12 (shared questions, Jaccard 0.02)
- **Major boundary pathways:** none

**Questions for this family:**

1. Is this one clinical area? If not, how should it be divided, and along what clinical line?
2. This family has no dominant symptom group or clinical area, so we have not named it. Is there a clinical grouping here that the metadata does not capture?
3. It overlaps strongly with HA_C48 (driver: shared SNOMED concepts). Are these one clinical area or two that share a vocabulary?
4. This is a very small family. Should it stand alone, or belong inside a larger one?

---

## Cross-cutting questions

### Features used across many families

424 questions, symptom discriminators, SNOMED concepts and dispositions are used by at least 5 candidate families. The most widely shared are:

| Type | Id | Description | Families | Pathways |
|---|---|---|---|---|
| Tx triage question | TX170003 |  | 26 | 219 |
| disposition code | DX012 | Emergency Ambulance Response (Category 3) | 22 | 404 |
| Tx triage question | TX221039 |  | 19 | 180 |
| Tx triage question | TX222414 |  | 18 | 42 |
| Tx triage question | TX222415 |  | 18 | 42 |
| Tx triage question | TX221449 |  | 14 | 514 |
| symptom discriminator | 4003 | PC full Primary Care assessment and prescribing capability | 14 | 514 |
| disposition code | DX02 | Refer to Treatment Centre within 1 hour | 14 | 405 |
| disposition code | DX11 | Speak to a Primary Care Service within 1 hour | 14 | 262 |
| disposition code | DX15 | Speak to a Primary Care Service within 24 hours | 14 | 94 |
| Tx triage question | TX221017 |  | 14 | 88 |
| disposition code | DX06 | To Contact a Primary Care Service within 6 hours | 13 | 386 |

**For each of these, we need to know:** is it one clinical concept used across many areas, several different concepts that share an identifier or wording, or a by-product of how the pathways were authored? The answer changes whether a shared structure would be correct or would conflate distinct clinical meanings.

### Age

Paediatric pathways can be read three ways, and the structure supports more than one. Should paediatric pathways be:

- their own families, separate from the adult equivalents;
- age variants inside the same family as the adult pathway; or
- a cross-cutting attribute that every family handles?

### Trauma

Likewise for trauma. Is trauma one family, several anatomical families, a cross-cutting dimension applied to other families, or a shared entry point into them?

### Safety

Is there any pair of candidate families that must not be separated, because a clinically critical route runs between them? This constraint cannot be seen in the data and has to come from clinical review.

---

_No architectural decision has been made. This review feeds the family definitions that Phase 3 will size and cost._
