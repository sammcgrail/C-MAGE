./fetch.sh: line 12: file: command not found
US6699871B2 | http=200 |  | 2567404B | pages=23 | https://patentimages.storage.googleapis.com/b2/13/04/e3584e05f9fb57/US6699871.pdf | 
./fetch.sh: line 12: file: command not found
US6936612B2 | http=200 |  | 5215075B | pages=41 | https://patentimages.storage.googleapis.com/21/cd/63/f2f69c1759732c/US6936612.pdf | 
./fetch.sh: line 12: file: command not found
US6627754B2 | http=200 |  | 1560172B | pages=14 | https://patentimages.storage.googleapis.com/4d/4c/fa/c539613d1b0480/US6627754.pdf | 
./fetch.sh: line 12: file: command not found
US7157456B2 | http=200 |  | 5066094B | pages=78 | https://patentimages.storage.googleapis.com/23/a6/e3/73234ee87e9b89/US7157456.pdf | 
./fetch.sh: line 12: file: command not found
US7514444B2 | http=200 |  | 7718462B | pages=74 | https://patentimages.storage.googleapis.com/0a/c0/5d/0995f0d53ffa42/US7514444.pdf | 
./fetch.sh: line 12: file: command not found
US8946235B2 | http=200 |  | 9686713B | pages=86 | https://patentimages.storage.googleapis.com/ef/74/2e/4705343cbcc18a/US8946235.pdf | 
./fetch.sh: line 12: file: command not found
US6469012B1 | http=200 |  | 5991395B | pages=47 | https://patentimages.storage.googleapis.com/94/31/5a/f42c0c80e296e6/US6469012.pdf | 
./fetch.sh: line 12: file: command not found
US5250534A | http=200 |  | 1361465B | pages=13 | https://patentimages.storage.googleapis.com/82/13/5f/0671691145ddb8/US5250534.pdf | 

## Nature of Google Patents PDFs (checked 5 files)
All patentimages PDFs: Producer ImageMagick, PDF 1.3, one 300-dpi CCITT bitonal page image per page (2320x3408 or 2560x3300), plus invisible Courier OCR text layer. Not vector. Same for 1993 and 2005 patents.
US6251910B1 | http=200 | application/pdf | 5511930B | pages=51 | https://patentimages.storage.googleapis.com/59/57/83/1e027dac127336/US6251910.pdf | 
US6515117B2 | http=200 | application/pdf | 1711721B | pages=16 | https://patentimages.storage.googleapis.com/12/f3/7f/ce116d471fde4e/US6515117.pdf | 
US6573293B2 | http=200 | application/pdf | 8414455B | pages=134 | https://patentimages.storage.googleapis.com/55/d4/8a/0d5a7ed0354e6b/US6573293.pdf | 
US7579449B2 | http=200 | application/pdf | 3539338B | pages=38 | https://patentimages.storage.googleapis.com/bb/6e/db/4d1ca30f0ae63c/US7579449.pdf | 
US5747498A | http=200 | application/pdf | 3222130B | pages=26 | https://patentimages.storage.googleapis.com/86/59/26/d32e343f4cc1e8/US5747498.pdf | 
US6362178B1 | http=200 | application/pdf | 5766533B | pages=146 | https://patentimages.storage.googleapis.com/b7/5f/16/6dfd86c9ac0872/US6362178.pdf | 

## Visual confirmation (90 dpi)
- US6699871B2 sitagliptin p12: Boc-protected beta-amino acid intermediate w/ wedge stereo, F/CF3-phenyl. p19: claims w/ Markush Ia/Ib/Ic + 2 explicit compounds. CONFIRMED.
- US6627754B2 tofacitinib p6: Preparation A/B + Scheme 1 pyrrolo[2,3-d]pyrimidine reaction schemes. p13: Markush formula I, II fragments. CONFIRMED.
- US6469012B1 sildenafil-use: 47p mostly citation lists + reexam cert; structures only p1,p8,p9,p13. REJECTED.
- Long ones rejected: US7157456 78p, US7514444 74p, US8946235 86p, US6573293 134p, US6362178 146p.

## Final set copied to /root/C-MAGE/MERMaid/pdfdir
- US6699871B2_sitagliptin.pdf 23p, US6627754B2_tofacitinib.pdf 14p, US7579449B2_empagliflozin.pdf 38p (p22 TIPS-alkynyl intermediates, p33 glucoside table w/ stereo CONFIRMED), US6936612B2_palbociclib.pdf 41p (p14,p16 schemes CONFIRMED)
- Optional extra kept in /tmp only: PMC11643494.pdf Molecules 2024 29(23):5494 CC BY, 19p, structures p3,p5-7 schemes, p8-13 SAR tables (600dpi CCITT stencils, vector text)
- USPTO image-ppubs downloadPdf URL -> 403 for curl. Google Patents citation_pdf_url route works with plain curl + browser UA.
