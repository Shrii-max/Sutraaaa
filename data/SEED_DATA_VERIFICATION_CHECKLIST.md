# Landmark Legal Precedents & Bare-Act Statutes: Provenance & Verification Checklist

**LexAgent Document Intelligence Platform**  
**Jurisdiction:** Republic of India  
**Status:** Pre-seeded Records (Default: `unverified`)  
**Auditor:** Principal Engineer & Independent QA Lead  

---

## 1. Overview & Counsel Verification Protocol

In compliance with **Hard Rule 4 (Zero Hallucinated Authorities)** and LexAgent Provenance Architecture, all judicial precedents and statutory bare-act sections loaded into the retrieval database must trace to verifiable primary sources (eCourts, Supreme Court of India digital reports, Indian Kanoon, or legislative gazettes via India Code).

Every pre-seeded record is marked with:
- `verification_status = 'unverified'`
- `source_url`: Verifiable primary or secondary legal repository URL
- `retrieved_on`: UTC timestamp of acquisition
- `verified_by`: Legal counsel sign-off identifier

Until an Indian Advocate on Record or Senior Counsel reviews and signs off on the ratio decidendi and text, the record displays an **"Unverified source"** badge in the Sutra UI and API responses.

---

## 2. Seeded Judicial Precedents (`judgments` Table)

| ID / Citation | Case Title & Bench | Court & Date | Source Repository URL | Verification Status | Counsel Sign-Off |
|---|---|---|---|---|---|
| `(2014) 10 SCC 473` | **Anvar P.V. v. P.K. Basheer and Others**<br>Bench: R.M. Lodha C.J., Kurian Joseph, R.F. Nariman JJ. | Supreme Court of India<br>2014-09-18 | [Indian Kanoon Doc 106676356](https://indiankanoon.org/doc/106676356/) | `unverified` | [ ] Pending Counsel Review |
| `(2020) 7 SCC 1` | **Arjun Panditrao Khotkar v. Kailash Kushanrao Gorantyal**<br>Bench: R.F. Nariman, S. Ravindra Bhat, V. Ramasubramanian JJ. | Supreme Court of India<br>2020-07-14 | [Indian Kanoon Doc 174426572](https://indiankanoon.org/doc/174426572/) | `unverified` | [ ] Pending Counsel Review |
| `(2021) 2 SCC 1` | **Vidya Drolia and Others v. Durga Trading Corporation**<br>Bench: N.V. Ramana, Sanjiv Khanna, Krishna Murari JJ. | Supreme Court of India<br>2020-12-14 | [Indian Kanoon Doc 135084931](https://indiankanoon.org/doc/135084931/) | `unverified` | [ ] Pending Counsel Review |
| `(2014) 9 SCC 129` | **Dashrath Rupsingh Rathod v. State of Maharashtra**<br>Bench: T.S. Thakur, Vikramajit Sen, C. Nagappan JJ. | Supreme Court of India<br>2014-08-01 | [Indian Kanoon Doc 184131566](https://indiankanoon.org/doc/184131566/) | `unverified` | [ ] Pending Counsel Review |
| `(2020) 15 SCC 1` | **Babulal Vardharji Gurjar v. Veer Gurjar Aluminium Industries**<br>Bench: A.M. Khanwilkar, Dinesh Maheshwari JJ. | Supreme Court of India<br>2020-08-14 | [Indian Kanoon Doc 171587327](https://indiankanoon.org/doc/171587327/) | `unverified` | [ ] Pending Counsel Review |

### Judicial Verification Steps for Counsel:
1. Verify citation against SCC / SCR official reporter.
2. Confirm bench composition and date of judgment.
3. Confirm `ratio_decidendi` reflects binding holding and not obiter dicta.
4. Verify whether the ruling has been modified, distinguished, or overruled by a larger bench (e.g. *Dashrath Rupsingh Rathod* modified by NI Amendment Act 2015; *Anvar P.V.* clarified by *Arjun Panditrao Khotkar*).
5. Execute verification update in DB:
   ```sql
   UPDATE judgments 
   SET verification_status = 'verified', 
       verified_by = 'Adv. <Bar_Enrollment_No>'
   WHERE citation = '(2014) 10 SCC 473';
   ```

---

## 3. Seeded Bare-Act Statutory Sections (`statute_sections` Table)

| Act & Section | Section Heading | Legislative Gazette URL | Verification Status | Counsel Sign-Off |
|---|---|---|---|---|
| **IPC Section 420** | Cheating and dishonestly inducing delivery of property | [India Code Act AC_CEN_5_23_00037](https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_00037_186045_1523266765688&sectionId=46200) | `unverified` | [ ] Pending Counsel Review |
| **IPC Section 406** | Punishment for criminal breach of trust | [India Code Act AC_CEN_5_23_00037](https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_00037_186045_1523266765688&sectionId=46186) | `unverified` | [ ] Pending Counsel Review |
| **NI Act Section 138** | Dishonour of cheque for insufficiency of funds | [India Code Act AC_CEN_2_10_00006](https://www.indiacode.nic.in/show-data?actid=AC_CEN_2_10_00006_188126_1523268870198&sectionId=42138) | `unverified` | [ ] Pending Counsel Review |
| **CrPC Section 156** | Police officer's power to investigate cognizable case | [India Code Act AC_CEN_5_23_000010](https://www.indiacode.nic.in/show-data?actid=AC_CEN_5_23_000010_197402_1517807320555&sectionId=34656) | `unverified` | [ ] Pending Counsel Review |

### Statutory Verification Steps for Counsel:
1. Verify statutory text against latest amended bare act on indiacode.nic.in.
2. Note transition mappings to Bharatiya Nyaya Sanhita (BNS) and Bharatiya Nagarik Suraksha Sanhita (BNSS).
3. Execute verification update in DB:
   ```sql
   UPDATE statute_sections 
   SET verification_status = 'verified', 
       verified_by = 'Adv. <Bar_Enrollment_No>'
   WHERE act = 'IPC' AND section_no = '420';
   ```

