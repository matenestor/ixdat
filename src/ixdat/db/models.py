from typing import List, Optional

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class MSMeasurementMixin:
    pass  # no special columns


class ECMeasurementMixin:
    ec_technique: Mapped[str]


class DBBase(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


class DBMeasurement(DBBase):
    __tablename__ = "measurement"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    sample_name: Mapped[Optional[str]]
    technique: Mapped[str]
    tstamp: Mapped[float]
    # metadata: Mapped[dict[str, str | int | float | bool]]
    # aliases: Mapped[dict[str, list[str]]]
    ixd_metadata = mapped_column(JSON)
    aliases = mapped_column(JSON)

    # DB attribute for SQLAlchemy polymorphism and Joined Table Inheritance
    # see: https://docs.sqlalchemy.org/en/20/orm/inheritance.html#joined-table-inheritance
    type: Mapped[str]

    # TODO @SQL shouldn't be like this? it it needs many2many relationship
    data_series: Mapped[List["DBDataSeries"]] = relationship(
        back_populates="measurement", cascade="all, delete-orphan"
    )

    __mapper_args__ = {
        "polymorphic_identity": "measurement",
        "polymorphic_on": "type",
    }

    def __repr__(self) -> str:
        return f"Measurement(id={self.id!r}, name={self.name!r}, technique={self.technique!r})"


class DBMSMeasurement(MSMeasurementMixin, DBMeasurement):
    __tablename__ = "ms_measurement"
    id: Mapped[int] = mapped_column(ForeignKey("measurement.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "ms_measurement",
    }

    def __repr__(self) -> str:
        return f"MSMeasurement(id={self.id!r})"


class DBECMeasurement(ECMeasurementMixin, DBMeasurement):
    __tablename__ = "ec_measurement"
    id: Mapped[int] = mapped_column(ForeignKey("measurement.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "ec_measurement",
    }

    def __repr__(self) -> str:
        return f"ECMeasurement(id={self.id!r})"


class DBECMSMeasurement(ECMeasurementMixin, MSMeasurementMixin, DBMeasurement):
    __tablename__ = "ecms_measurement"
    id: Mapped[int] = mapped_column(ForeignKey("measurement.id"), primary_key=True)

    __mapper_args__ = {
        "polymorphic_identity": "ecms_measurement",
    }

    def __repr__(self) -> str:
        return f"ECMSMeasurement(id={self.id!r})"


class DBDataSeries(DBBase):
    __tablename__ = "data_series"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    data: Mapped[float]
    measurement: Mapped["DBMeasurement"] = relationship(back_populates="data_series")

    measurement_id: Mapped[int] = mapped_column(ForeignKey("measurement.id"))

    def __repr__(self) -> str:
        return f"DataSeries(id={self.id!r}, data={self.data!r})"


# TODO @SQLA
class DBTimeSeries(DBBase):
    __tablename__ = "time_series"
    id: Mapped[int] = mapped_column(primary_key=True)


# TODO @SQLA
class DBValueSeries(DBBase):
    __tablename__ = "value_series"
    id: Mapped[int] = mapped_column(primary_key=True)


# TODO @SQLA
class DBConstantSeries(DBBase):
    __tablename__ = "constant_series"
    id: Mapped[int] = mapped_column(primary_key=True)
