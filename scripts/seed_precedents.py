"""Seed landmark Indian legal precedents into local database.

Enforces Hard Rule 4: LLM can only retrieve and summarize verified cases from DB.
"""

from app.db.session import get_engine, init_db, get_session_factory
from app.db.models import PrecedentCaseModel
from app.llm.embedding import get_embedding_client

LANDMARK_INDIAN_PRECEDENTS = [
    {
        "case_title": "Anvar P.V. v. P.K. Basheer and Others",
        "citation": "(2014) 10 SCC 473",
        "court": "Supreme Court of India",
        "judgment_date": "2014-09-18",
        "bench": "R.M. Lodha, C.J., Kurian Joseph, R.F. Nariman, JJ.",
        "summary": "Landmark ruling on the admissibility of electronic records and secondary evidence under the Indian Evidence Act, 1872.",
        "ratio_decidendi": "An electronic record by way of secondary evidence shall not be admitted in evidence unless the mandatory requirements and certificate contemplated under Section 65B(4) of the Evidence Act are satisfied. Oral evidence cannot substitute the mandatory certificate under Section 65B.",
    },
    {
        "case_title": "Arjun Panditrao Khotkar v. Kailash Kushanrao Gorantyal",
        "citation": "(2020) 7 SCC 1",
        "court": "Supreme Court of India",
        "judgment_date": "2020-07-14",
        "bench": "R.F. Nariman, S. Ravindra Bhat, V. Ramasubramanian, JJ.",
        "summary": "Clarified Section 65B certificate timing and procedural compliance for electronic evidence in trials.",
        "ratio_decidendi": "The certificate required under Section 65B(4) is a condition precedent to the admissibility of electronic evidence as secondary evidence. The certificate should ideally be produced when the electronic record is produced, but the court may allow it to be filed prior to the trial concluding.",
    },
    {
        "case_title": "Vidya Drolia and Others v. Durga Trading Corporation",
        "citation": "(2021) 2 SCC 1",
        "court": "Supreme Court of India",
        "judgment_date": "2020-12-14",
        "bench": "N.V. Ramana, Sanjiv Khanna, Krishna Murari, JJ.",
        "summary": "Fourfold test for determining non-arbitrability of disputes under the Arbitration and Conciliation Act, 1996.",
        "ratio_decidendi": "A dispute is non-arbitrable when: (1) it relates to actions in rem; (2) affects third-party rights or has erga omnes effect; (3) pertains to inalienable sovereign functions; or (4) is expressly or by necessary implication non-arbitrable under a specific statute.",
    },
    {
        "case_title": "Dashrath Rupsingh Rathod v. State of Maharashtra",
        "citation": "(2014) 9 SCC 129",
        "court": "Supreme Court of India",
        "judgment_date": "2014-08-01",
        "bench": "T.S. Thakur, Vikramajit Sen, C. Nagappan, JJ.",
        "summary": "Territorial jurisdiction of Magistrate Courts in Section 138 Negotiable Instruments Act dishonour of cheque complaints.",
        "ratio_decidendi": "Jurisdiction to file a complaint under Section 138 of the Negotiable Instruments Act lies where the drawee bank is located (subsequently amended by the Negotiable Instruments Amendment Act 2015 to locate jurisdiction at the branch where payee maintains their account).",
    },
    {
        "case_title": "Babulal Vardharji Gurjar v. Veer Gurjar Aluminium Industries Pvt. Ltd.",
        "citation": "(2020) 15 SCC 1",
        "court": "Supreme Court of India",
        "judgment_date": "2020-08-14",
        "bench": "A.M. Khanwilkar, Dinesh Maheshwari, JJ.",
        "summary": "Applicability of Article 137 of the Limitation Act, 1963 to insolvency petitions under the Insolvency and Bankruptcy Code, 2016.",
        "ratio_decidendi": "The period of limitation for filing an application under Section 7 of the IBC is three years governed by Article 137 of the Limitation Act, 1963, commencing from the date when default occurred. An acknowledgement under Section 18 can extend limitation only if pleaded with specific foundation.",
    },
]


def seed():
    engine = get_engine()
    init_db(engine)
    factory = get_session_factory()
    session = factory()

    embed_client = get_embedding_client()
    count = 0

    try:
        for p in LANDMARK_INDIAN_PRECEDENTS:
            existing = session.query(PrecedentCaseModel).filter_by(citation=p["citation"]).first()
            if not existing:
                corpus = f"{p['case_title']} {p['summary']} {p['ratio_decidendi']}"
                emb = embed_client.embed_query(corpus)
                case_obj = PrecedentCaseModel(
                    case_title=p["case_title"],
                    citation=p["citation"],
                    court=p["court"],
                    judgment_date=p["judgment_date"],
                    bench=p["bench"],
                    summary=p["summary"],
                    ratio_decidendi=p["ratio_decidendi"],
                    full_text=p["summary"],
                    embedding=emb,
                )
                session.add(case_obj)
                count += 1
        session.commit()
        print(f"Successfully seeded {count} landmark Indian precedents into database.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()

