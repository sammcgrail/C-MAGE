# Score: batch7 corpus_rerender_1500

Manifest `manifest_corpus_rerender_15007.json` (corpus_rerender_1500_7); threshold 0.8431.

- Drawn molecules (recall denominator): **200**
- Structures emitted for those groups (precision denominator): **200**
- Stage 1 figures: n/a; stage 2 segments: 200

| metric | stereo required | stereo relaxed |
|---|---|---|
| recall | 121/200 = 0.605 | 146/200 = 0.73 |
| precision | 121/200 = 0.605 | 146/200 = 0.73 |

Structures by verdict: exact 121, stereo 25, wrong 34, invalid 20

## Confidence split vs correctness

| tier | n | exact | stereo | wrong | invalid | wrong+invalid | exact |
|---|---|---|---|---|---|---|---|
| high | 127 | 107 | 10 | 9 | 1 | 0.0787 | 0.8425 |
| low | 73 | 14 | 15 | 25 | 19 | 0.6027 | 0.1918 |

## Graded verdicts -- what the strict `wrong` pile is made of

The strict counts above are unchanged. Below, each structure is graded by the
LOOSEST relaxation needed before it and the drawn molecule agree. `near` (Tanimoto >= 0.85) is a **diagnostic, not a pass** -- Morgan fingerprints
are stereo-blind, so two diastereomers score 1.000. Gate: `graded_selftest.py`.

| grade | structures | % | + largest fragment | needed decode | needed dephantom |
|---|---|---|---|---|---|
| exact | 122 | 61.0% | 122 | 0 | 0 |
| stereo | 25 | 12.5% | 26 | 0 | 0 |
| salt | 2 | 1.0% | 2 | 0 | 0 |
| near | 5 | 2.5% | 5 | 0 | 0 |
| wrong | 26 | 13.0% | 25 | 0 | 0 |
| invalid | 20 | 10.0% | 20 | 0 | 0 |

Of the **34** structures the strict metric calls `wrong`:

- same molecule, different representation: **3** (8.8%)
- near-miss (skeleton match or Tanimoto >= 0.85): 5
- genuinely different molecule: 26

| recall | molecules |
|---|---|
| strict, stereo required | 121/200 |
| any matched grade (exact/stereo/tautomer/charge/salt) | 149/200 |

Recall by grade: exact 122, stereo 25, salt 2, no 51


## Per group

| group | drawn | figs | segs | structs | rec.exact | rec.stereo | exact | stereo | wrong | invalid | high | low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1_8_naphthyridine_3_carboxylic_acid_7_1alpha_5alpha_6alpha_6_cid62959 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| 2_fluoro_2_deoxy_d_glucose_cid170049 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| 3_iodobenzylguanidine_cid60860 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| 5_7_diiodo_8_hydroxyquinoline_cid3728 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| 7_chloro_2_methylimino_5_phenyl_2_3_dihydro_4h_1_4_benzodiaz_cid2712 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| acetrizoic_acid_cid6806 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| alfentanil_cid51263 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| aluminum_hydroxide_cid10176082 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| aminorex_cid16630 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| amitraz_cid36324 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| amphetamine_cid3007 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| antimony_potassium_tartrate_cid73415808 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| apigenin_cid5280443 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| arecoline_cid2230 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| arsanilic_acid_cid7389 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| arsenic_trioxide_cid14888 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| arsphenamine_cid8774 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| artemether_cid68911 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| artesunate_cid6917864 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| astemizole_cid2247 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| bacampicillin_cid441397 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| barium_sulfate_cid24414 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| betamethasone_valerate_cid16533 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| betazole_cid7741 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| bismuth_subcitrate_cid10101269 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| bithionol_cid2406 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| boro_scopol_cid3000322 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| bortezomib_cid387447 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| butorphanol_cid5361092 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| capsaicin_cid1548943 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| carprofen_cid2581 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| cefcapene_pivoxil_cid5282438 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| cefpodoxime_proxetil_cid6526396 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| ceftiofur_cid6328657 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| cefuroxime_axetil_cid6321416 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| cephaeline_cid442195 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| chloral_hydrate_cid2707 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| chlormerodrin_cid25210 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| ciclesonide_cid6918155 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| cisapride_cid6917698 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| clenbuterol_cid2783 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| clomethiazole_cid10783 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| clonazepam_cid2802 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| clopidol_cid18087 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| clorsulon_cid43231 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| cocaine_cid446220 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| crisaborole_cid44591583 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| cythioate_cid8293 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| dabigatran_etexilate_cid135565674 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| danofloxacin_cid71335 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| daunorubicin_cid30323 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| deferasirox_cid214348 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| deferiprone_cid2972 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| deferoxamine_cid2973 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| delorazepam_cid17925 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| deltamethrin_cid40585 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| diatrizoate_cid2140 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| didanosine_cid135398739 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| diethylstilbestrol_cid448537 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| dimercaprol_cid3080 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| diodon_cid5284574 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| dotatate_cid11170867 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ebselen_cid3194 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| edetate_calcium_disodium_anhydrous_cid6093170 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| emetine_cid10219 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| enrofloxacin_cid71188 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| epirubicin_cid41867 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| ergotamine_cid8223 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| erythromycin_estolate_cid441371 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| estramustine_cid259331 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| ethylenediaminetetra_methylenephosphonic_acid_cid15025 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| fenbendazole_cid3334 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| fenfluramine_cid3337 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| ferric_citrate_cid61300 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| fipronil_cid3352 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| florbetapir_f_18_cid24822371 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| florfenicol_cid114811 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| fluralaner_cid25144319 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| fosamprenavir_cid131536 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| fusidic_acid_cid3000226 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| gadodiamide_cid153921 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| gadopentetic_acid_cid6857474 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| gadoteric_acid_cid158536 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| gadoxetic_acid_cid25203894 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| galantamine_cid9651 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| gallium_nitrate_cid61635 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| ginkgolide_b_cid11973122 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| gold_sodium_thiomalate_cid22318 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| griseofulvin_cid441140 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| heroin_cid5462328 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| hesperidin_cid10621 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| hmpao_cid9552071 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| huperzine_a_cid854026 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| hydrocodone_cid5284569 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| hydromorphone_cid5284570 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| hydroxocobalamin_cid44475014 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| icariin_cid5318997 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| indocyanine_green_cid5282412 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| iobitridol_cid65985 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| iodixanol_cid3724 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| ioflupane_cid10048368 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| iohexol_cid3730 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| iopamidol_cid65492 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| iopromide_cid3736 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| ioversol_cid3741 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| isavuconazonium_cid6918606 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| isoflurane_cid3763 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| lanthanum_carbonate_anhydrous_cid168924 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| levamisole_cid26879 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| lisdexamfetamine_cid11597698 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| lobaplatin_cid10000860 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| lobeline_cid101616 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| lysergic_acid_diethylamide_cid5761 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| magnesium_2_pyrrolidone_5_carboxylate_cid18601084 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| mangafodipir_cid76967443 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| maropitant_cid204108 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| medetomidine_cid68602 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| medronic_acid_cid16124 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| mephobarbital_cid8271 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| mescaline_cid4076 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| mesoridazine_cid4078 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| metamizole_cid3111 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| methamphetamine_cid10836 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| methaqualone_cid6292 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| metrizamide_cid443944 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| mibefradil_cid60663 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| midazolam_cid4192 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| molnupiravir_cid145996610 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| monensin_cid441145 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| motexafin_lutetium_cid3081907 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| moxidectin_cid9832912 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| mupirocin_cid446596 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| nabumetone_cid4409 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| nalidixic_acid_cid4421 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| nedaplatin_cid9796440 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| nicomorphine_cid5362460 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| nitrofurazone_cid5447130 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| noscapine_cid275196 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| oclacitinib_cid44631938 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| olsalazine_cid22419 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| oridonin_cid5321010 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| oxymorphone_cid5284604 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| padeliporfin_cid171041442 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| palifosfamide_cid100427 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| papaverine_cid4680 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| pentazocine_cid441278 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| pentetreotide_cid72128 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| phenacetin_cid4754 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| phenoperidine_cid11226 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| phentermine_cid4771 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| physostigmine_cid5983 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| pilocarpine_cid5910 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| pimobendan_cid4823 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| pinazepam_cid40391 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| ponazuril_cid3050408 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| potassium_iodide_cid4875 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| prasugrel_cid6918456 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| quinidine_cid441074 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| quinine_cid3034034 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| regadenoson_cid219024 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| remifentanil_cid60815 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| reserpine_cid5770 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| rimonabant_cid104850 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| rofecoxib_cid5090 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| sarolaner_cid73169092 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| selamectin_cid9578507 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| sibutramine_cid5210 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| silver_sulfadiazine_cid441244 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |
| sp_4_2_1r_2r_1_2_cyclohexanediamine_kappan1_kappan2_bis_tetr_cid9832045 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| sparfloxacin_cid60464 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| stavudine_cid18283 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| strontium_ranelate_cid6918182 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| succimer_cid2724354 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| sufentanil_cid41693 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| sulfathiazole_cid5340 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| suramin_cid5361 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| tapentadol_cid9838022 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| tegafur_cid5386 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| tegaserod_cid135409453 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| temoporfin_cid60751 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| tenofovir_alafenamide_cid9574768 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| tenofovir_disoproxil_cid5481350 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| terfenadine_cid5405 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| tetrofosmin_cid4274 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| titanium_dioxide_cid26042 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| toltrazuril_cid68591 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| travoprost_cid5282226 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| triamcinolone_acetonide_cid6436 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| triclabendazole_cid50248 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| troglitazone_cid5591 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| troleandomycin_cid202225 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 |
| tubocurarine_cid6000 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| unoprostone_cid5311236 | 1 | None | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| valdecoxib_cid119607 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| valganciclovir_cid135413535 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| vindesine_cid40839 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| xylazine_cid5707 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| zinc_acetate_cid11192 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 |
| zopiclone_cid5735 | 1 | None | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 |
| zotarolimus_cid9876378 | 1 | None | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
