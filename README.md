models.py:
Why two seperate tables (RedditComment and SentimentResult):
    - Enforces the deduplication contract
        - WE check if comment_id exists in RedditComment before running the NLP on it
    - Lets us re-reun ML analysis in isolation without the need to rescrape