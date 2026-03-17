from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship
from .database import Base


# Raw data from scraper, each row is one reddit comment
class RedditComment(Base):
    __tablename__ = "reddit_comments"

    id = Column(Integer, primary_key=True, index=True)

    # Unique Reddit comment ID
    # Deduplication key: before running NLP the scraper checks to see if it exists
    comment_id = Column(String, unique=True, nullable=False, index=True)
    player_name = Column(String, nullable=False, index=True)

    body = Column(Text, nullable=False)
    subreddit = Column(String, nullable=False)
    score = Column(Integer, default=0)
    created_utc = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)

    sentiment = relationship(
        "SentimentResult",
        back_populates="comment",
        uselist=False,
        cascade="all, delete"
    )

    __table_args__ = (
        Index("ix_player_created", "player_name", "created_utc"),
    )


# The ML output for a given comment
class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True, index=True)

    comment_id = Column(
        Integer,
        ForeignKey("reddit_comments.id", ondelete="CASCADE"),
        unique=True,  # Enforces the 1:1 relationship at the DB level
        nullable=False
    )

    # HuggingFace output label: "POSITIVE", "NEGATIVE", or "NEUTRAL"
    label = Column(String, nullable=False)

    # The model's confidence score for that label (0.0 to 1.0)
    score = Column(Float, nullable=False)

    analyzed_at = Column(DateTime, default=datetime.utcnow)
    comment = relationship("RedditComment", back_populates="sentiment")