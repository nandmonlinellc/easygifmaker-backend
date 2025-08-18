from .user import db  # reuse the existing db instance
from datetime import datetime

class JobMetric(db.Model):
    __tablename__ = 'job_metrics'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # identity
    tool = db.Column(db.String(64), index=True)  # add-text, add-text-layers, resize, optimize, video-to-gif, gif-maker, crop
    task_id = db.Column(db.String(64), index=True)
    status = db.Column(db.String(16), index=True)  # SUCCESS | FAILURE
    error_message = db.Column(db.Text, nullable=True)

    # input characteristics
    input_type = db.Column(db.String(32))  # gif|video|images
    input_width = db.Column(db.Integer)
    input_height = db.Column(db.Integer)
    input_frames = db.Column(db.Integer)
    input_size_bytes = db.Column(db.BigInteger)

    # output characteristics
    output_size_bytes = db.Column(db.BigInteger)

    # performance
    processing_time_ms = db.Column(db.Integer)

    # options snapshot (short JSON-like string)
    options = db.Column(db.String(512))  # e.g., "layers=3; anim=fade; colors=128; lossy=80"

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'tool': self.tool,
            'task_id': self.task_id,
            'status': self.status,
            'error_message': self.error_message,
            'input_type': self.input_type,
            'input_width': self.input_width,
            'input_height': self.input_height,
            'input_frames': self.input_frames,
            'input_size_bytes': self.input_size_bytes,
            'output_size_bytes': self.output_size_bytes,
            'processing_time_ms': self.processing_time_ms,
            'options': self.options,
        }


class DailyMetric(db.Model):
    __tablename__ = 'daily_metrics'

    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, index=True)
    tool = db.Column(db.String(64), index=True)
    total = db.Column(db.Integer)
    failures = db.Column(db.Integer)
    p95_ms = db.Column(db.Integer)
    avg_ms = db.Column(db.Integer)

    __table_args__ = (
        db.UniqueConstraint('day', 'tool', name='uix_day_tool'),
    )

    def to_dict(self):
        return {
            'day': self.day.isoformat(),
            'tool': self.tool,
            'total': self.total,
            'failures': self.failures,
            'p95_ms': self.p95_ms,
            'avg_ms': self.avg_ms,
        }
