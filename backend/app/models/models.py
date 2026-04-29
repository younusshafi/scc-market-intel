"""Database models for the SCC Market Intelligence Module."""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Boolean, Float,
    JSON, Index, func,
)
from app.core.database import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_number = Column(String(100), index=True)
    tender_number_en = Column(String(100), nullable=True)

    # Bilingual fields
    tender_name_ar = Column(Text, nullable=True)
    tender_name_en = Column(Text, nullable=True)
    entity_ar = Column(String(300), nullable=True)
    entity_en = Column(String(300), nullable=True)
    category_ar = Column(String(200), nullable=True)
    category_en = Column(String(200), nullable=True)
    grade_ar = Column(String(100), nullable=True)
    grade_en = Column(String(100), nullable=True)
    tender_type_ar = Column(String(200), nullable=True)
    tender_type_en = Column(String(200), nullable=True)

    # Dates
    sales_end_date = Column(Date, nullable=True)
    bid_closing_date = Column(Date, nullable=True)
    actual_opening_date = Column(Date, nullable=True)

    # Financials
    fee = Column(Float, nullable=True)
    bank_guarantee = Column(String(50), nullable=True)

    # Classification
    view = Column(String(50))  # NewTenders, InProcessTenders, SubContractTenders
    is_retender = Column(Boolean, default=False)
    is_scc_relevant = Column(Boolean, default=False)
    is_subcontract = Column(Boolean, default=False)

    # Parent tender (for re-tenders)
    parent_tender_number = Column(String(100), nullable=True)
    parent_tender_name = Column(Text, nullable=True)

    # Raw data backup
    raw_data = Column(JSON, nullable=True)

    # Metadata
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now(), onupdate=func.now())
    scraped_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_tender_scc", "is_scc_relevant"),
        Index("ix_tender_view", "view"),
        Index("ix_tender_closing", "bid_closing_date"),
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(200))
    title = Column(Text)
    link = Column(Text, unique=True)
    published = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)

    # Classification
    is_competitor_mention = Column(Boolean, default=False)
    mentioned_competitors = Column(JSON, nullable=True)  # list of competitor names
    is_relevant = Column(Boolean, default=True)

    scraped_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_news_source", "source"),
        Index("ix_news_published", "published"),
        Index("ix_news_competitor", "is_competitor_mention"),
    )


class Briefing(Base):
    __tablename__ = "briefings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_md = Column(Text)
    content_html = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=func.now())
    context_summary = Column(Text, nullable=True)  # what data went into the briefing
    model_used = Column(String(100), nullable=True)
    token_usage = Column(JSON, nullable=True)


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scrape_type = Column(String(50))  # tenders, news, competitor
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20))  # success, partial, failed
    records_found = Column(Integer, default=0)
    records_new = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)


class TenderProbe(Base):
    """Stores deep-probed tender detail data (bidders, purchasers, NIT)."""
    __tablename__ = "tender_probes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_number = Column(String(100), index=True, unique=True)
    tender_name = Column(Text, nullable=True)
    entity = Column(String(300), nullable=True)
    category = Column(String(200), nullable=True)
    fee = Column(Float, nullable=True)
    view = Column(String(50), nullable=True)

    # Probed detail data stored as JSON
    bidders = Column(JSON, nullable=True)      # [{company, offer_type, quoted_value, status}]
    purchasers = Column(JSON, nullable=True)    # [{company, purchase_date}]
    nit = Column(JSON, nullable=True)           # {title, governorate, scope, ...}

    probed_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CompetitorMention(Base):
    __tablename__ = "competitor_mentions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competitor_name = Column(String(100), index=True)
    source_type = Column(String(20))  # news, tender
    source_id = Column(Integer)  # FK to news_articles.id or tenders.id
    context = Column(Text, nullable=True)  # snippet of where they were mentioned
    detected_at = Column(DateTime, default=func.now())
