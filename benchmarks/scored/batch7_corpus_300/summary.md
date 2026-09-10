# Score: batch7 corpus_300

Manifest `manifest_corpus_3007.json` (corpus_300_7); threshold 0.8431.

- Drawn molecules (recall denominator): **200**
- Structures emitted for those groups (precision denominator): **200**
- Stage 1 figures: n/a; stage 2 segments: 200

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 20/200 = 0.1 | 27/200 = 0.135 |
| precision | 20/200 = 0.1 | 27/200 = 0.135 |

Structures by verdict: exact 20, stereo 7, wrong 145, invalid 28

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 34 | 9 | 0 | 24 | 1 | 0.7353 | 0.2647 |
| low | 166 | 11 | 7 | 121 | 27 | 0.8916 | 0.0663 |

## Graded verdicts -- what the strict `wrong` pile is made of

The strict counts above are unchanged. Below, each structure is graded by the
LOOSEST relaxation needed before it and the drawn molecule agree. `near` (Tanimoto >= 0.85) is a **diagnostic, not a pass** -- Morgan fingerprints
are stereo-blind, so two diastereomers score 1.000. Gate: `graded_selftest.py`.

| grade | structures | % | + largest fragment | needed decode | needed dephantom |
|---|---|---|---|---|---|
| exact | 110 | 55.0% | 117 | 0 | 89 |
| stereo | 18 | 9.0% | 19 | 0 | 11 |
| charge | 3 | 1.5% | 3 | 0 | 3 |
| salt | 7 | 3.5% | 1 | 0 | 0 |
| skeleton | 2 | 1.0% | 2 | 0 | 1 |
| near | 4 | 2.0% | 5 | 0 | 0 |
| wrong | 28 | 14.0% | 25 | 0 | 0 |
| invalid | 28 | 14.0% | 28 | 0 | 0 |

Of the **145** structures the strict metric calls `wrong`:

- same molecule, different representation: **111** (76.5%)
- near-miss (skeleton match or Tanimoto >= 0.85): 6
- genuinely different molecule: 28

| recall | molecules |
|---|---|
| strict, stereo required | 20/200 |
| any matched grade (exact/stereo/tautomer/charge/salt) | 138/200 |

Recall by grade: exact 110, stereo 18, charge 3, salt 7, no 62


## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1_8_naphthyridine_3_carboxylic_acid_7_1alpha_5alpha_6alpha_6_cid62959 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| 2_fluoro_2_deoxy_d_glucose_cid170049 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| 3_iodobenzylguanidine_cid60860 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| 5_7_diiodo_8_hydroxyquinoline_cid3728 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| 7_chloro_2_methylimino_5_phenyl_2_3_dihydro_4h_1_4_benzodiaz_cid2712 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| acetrizoic_acid_cid6806 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| alfentanil_cid51263 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| aluminum_hydroxide_cid10176082 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| aminorex_cid16630 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| amitraz_cid36324 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| amphetamine_cid3007 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| antimony_potassium_tartrate_cid73415808 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| apigenin_cid5280443 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| arecoline_cid2230 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| arsanilic_acid_cid7389 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| arsenic_trioxide_cid14888 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| arsphenamine_cid8774 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| artemether_cid68911 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| artesunate_cid6917864 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| astemizole_cid2247 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| bacampicillin_cid441397 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| barium_sulfate_cid24414 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| betamethasone_valerate_cid16533 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| betazole_cid7741 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| bismuth_subcitrate_cid10101269 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| bithionol_cid2406 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| boro_scopol_cid3000322 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| bortezomib_cid387447 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| butorphanol_cid5361092 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| capsaicin_cid1548943 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| carprofen_cid2581 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| cefcapene_pivoxil_cid5282438 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| cefpodoxime_proxetil_cid6526396 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ceftiofur_cid6328657 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| cefuroxime_axetil_cid6321416 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| cephaeline_cid442195 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| chloral_hydrate_cid2707 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| chlormerodrin_cid25210 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ciclesonide_cid6918155 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| cisapride_cid6917698 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| clenbuterol_cid2783 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| clomethiazole_cid10783 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| clonazepam_cid2802 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| clopidol_cid18087 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| clorsulon_cid43231 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| cocaine_cid446220 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| crisaborole_cid44591583 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| cythioate_cid8293 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| dabigatran_etexilate_cid135565674 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| danofloxacin_cid71335 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| daunorubicin_cid30323 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| deferasirox_cid214348 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| deferiprone_cid2972 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| deferoxamine_cid2973 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| delorazepam_cid17925 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| deltamethrin_cid40585 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| diatrizoate_cid2140 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| didanosine_cid135398739 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| diethylstilbestrol_cid448537 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| dimercaprol_cid3080 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| diodon_cid5284574 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| dotatate_cid11170867 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| ebselen_cid3194 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| edetate_calcium_disodium_anhydrous_cid6093170 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| emetine_cid10219 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| enrofloxacin_cid71188 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| epirubicin_cid41867 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ergotamine_cid8223 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| erythromycin_estolate_cid441371 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| estramustine_cid259331 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| ethylenediaminetetra_methylenephosphonic_acid_cid15025 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| fenbendazole_cid3334 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| fenfluramine_cid3337 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ferric_citrate_cid61300 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| fipronil_cid3352 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| florbetapir_f_18_cid24822371 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| florfenicol_cid114811 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| fluralaner_cid25144319 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| fosamprenavir_cid131536 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| fusidic_acid_cid3000226 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| gadodiamide_cid153921 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| gadopentetic_acid_cid6857474 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| gadoteric_acid_cid158536 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| gadoxetic_acid_cid25203894 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| galantamine_cid9651 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| gallium_nitrate_cid61635 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| ginkgolide_b_cid11973122 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| gold_sodium_thiomalate_cid22318 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| griseofulvin_cid441140 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| heroin_cid5462328 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| hesperidin_cid10621 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| hmpao_cid9552071 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| huperzine_a_cid854026 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| hydrocodone_cid5284569 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| hydromorphone_cid5284570 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| hydroxocobalamin_cid44475014 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| icariin_cid5318997 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| indocyanine_green_cid5282412 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| iobitridol_cid65985 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| iodixanol_cid3724 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| ioflupane_cid10048368 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| iohexol_cid3730 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| iopamidol_cid65492 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| iopromide_cid3736 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ioversol_cid3741 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| isavuconazonium_cid6918606 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| isoflurane_cid3763 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| lanthanum_carbonate_anhydrous_cid168924 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| levamisole_cid26879 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| lisdexamfetamine_cid11597698 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| lobaplatin_cid10000860 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| lobeline_cid101616 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| lysergic_acid_diethylamide_cid5761 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| magnesium_2_pyrrolidone_5_carboxylate_cid18601084 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| mangafodipir_cid76967443 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| maropitant_cid204108 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| medetomidine_cid68602 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| medronic_acid_cid16124 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| mephobarbital_cid8271 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| mescaline_cid4076 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| mesoridazine_cid4078 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| metamizole_cid3111 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| methamphetamine_cid10836 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| methaqualone_cid6292 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| metrizamide_cid443944 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| mibefradil_cid60663 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| midazolam_cid4192 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| molnupiravir_cid145996610 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| monensin_cid441145 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| motexafin_lutetium_cid3081907 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| moxidectin_cid9832912 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| mupirocin_cid446596 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| nabumetone_cid4409 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| nalidixic_acid_cid4421 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| nedaplatin_cid9796440 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| nicomorphine_cid5362460 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| nitrofurazone_cid5447130 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| noscapine_cid275196 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| oclacitinib_cid44631938 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| olsalazine_cid22419 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| oridonin_cid5321010 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| oxymorphone_cid5284604 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| padeliporfin_cid171041442 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| palifosfamide_cid100427 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| papaverine_cid4680 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| pentazocine_cid441278 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| pentetreotide_cid72128 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| phenacetin_cid4754 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| phenoperidine_cid11226 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| phentermine_cid4771 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| physostigmine_cid5983 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| pilocarpine_cid5910 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| pimobendan_cid4823 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| pinazepam_cid40391 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ponazuril_cid3050408 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| potassium_iodide_cid4875 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| prasugrel_cid6918456 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| quinidine_cid441074 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| quinine_cid3034034 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| regadenoson_cid219024 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| remifentanil_cid60815 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| reserpine_cid5770 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| rimonabant_cid104850 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| rofecoxib_cid5090 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| sarolaner_cid73169092 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| selamectin_cid9578507 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| sibutramine_cid5210 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| silver_sulfadiazine_cid441244 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| sp_4_2_1r_2r_1_2_cyclohexanediamine_kappan1_kappan2_bis_tetr_cid9832045 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| sparfloxacin_cid60464 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| stavudine_cid18283 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| strontium_ranelate_cid6918182 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| succimer_cid2724354 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| sufentanil_cid41693 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| sulfathiazole_cid5340 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| suramin_cid5361 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| tapentadol_cid9838022 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| tegafur_cid5386 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| tegaserod_cid135409453 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| temoporfin_cid60751 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| tenofovir_alafenamide_cid9574768 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| tenofovir_disoproxil_cid5481350 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| terfenadine_cid5405 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| tetrofosmin_cid4274 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| titanium_dioxide_cid26042 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| toltrazuril_cid68591 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| travoprost_cid5282226 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| triamcinolone_acetonide_cid6436 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| triclabendazole_cid50248 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| troglitazone_cid5591 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| troleandomycin_cid202225 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| tubocurarine_cid6000 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| unoprostone_cid5311236 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| valdecoxib_cid119607 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| valganciclovir_cid135413535 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| vindesine_cid40839 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| xylazine_cid5707 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| zinc_acetate_cid11192 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| zopiclone_cid5735 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| zotarolimus_cid9876378 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
