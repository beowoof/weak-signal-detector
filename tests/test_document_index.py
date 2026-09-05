import hashlib

from wsf.document_index import DocumentIndex, chunk_document, lexical_score


def test_chunks_are_exact_slices_of_the_source():
    text = "First paragraph about Yelnya.\n\nSecond paragraph about travel advice.\n\nThird."
    chunks = chunk_document(text)
    assert chunks
    for chunk in chunks:
        assert text[chunk["start"] : chunk["end"]] == chunk["text"]


def test_index_retrieves_the_relevant_admitted_passage(tmp_path):
    docs = [
        {
            "url": "https://example.com/yelnya",
            "text": "Commercial imagery showed tents at Yelnya. Rail movements continued south.",
            "content_sha256": hashlib.sha256(
                b"Commercial imagery showed tents at Yelnya. Rail movements continued south."
            ).hexdigest(),
            "source_tier": "preferred",
            "version_at": "2022-02-11T00:00:00+00:00",
        },
        {
            "url": "https://example.com/cookies",
            "text": "We use cookies to make this website work. Preference centre. Privacy.",
            "content_sha256": hashlib.sha256(
                b"We use cookies to make this website work. Preference centre. Privacy."
            ).hexdigest(),
            "source_tier": "fallback",
            "version_at": "2022-02-11T00:00:00+00:00",
        },
    ]

    def embed(texts):
        return [
            [1.0, 0.0] if "Yelnya" in text or "imagery" in text else [0.0, 1.0] for text in texts
        ]

    index = DocumentIndex(tmp_path, embed=embed)
    counts = index.upsert(docs)
    assert sum(counts.values()) >= 2
    hits = index.query(["satellite imagery troop tents Yelnya"], limit=2)
    assert hits
    assert "Yelnya" in hits[0]["text"]
    assert hits[0]["retrieval"] == "embedding"
    again = DocumentIndex(tmp_path, embed=embed)
    assert again.upsert(docs) == counts


def test_lexical_fallback_when_embeddings_are_missing(tmp_path):
    text = "FCDO advised against all travel to Ukraine while commercial means remained available."
    index = DocumentIndex(tmp_path, embed=None)
    index.upsert(
        [
            {
                "url": "https://www.gov.uk/foreign-travel-advice/ukraine",
                "text": text,
                "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        ]
    )
    hits = index.query(["FCDO travel advice Ukraine"], limit=3)
    assert hits
    assert hits[0]["retrieval"] == "lexical"
    assert "FCDO" in hits[0]["text"]
    assert lexical_score("cookies", text) < lexical_score("FCDO Ukraine", text)
