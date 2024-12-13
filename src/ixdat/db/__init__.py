from .models import (
    DBMeasurement,
    DBMSMeasurement,
    DBECMeasurement,
    DBECMSMeasurement,
    DBDataSeries,
    DBTimeSeries,
    DBValueSeries,
    DBConstantSeries
)


SAVEABLE_TO_DATABASE_MODEL = {
    "Measurement": DBMeasurement,
    "MSMeasurement": DBMSMeasurement,
    "ECMeasurement": DBECMeasurement,
    "ECMSMeasurement": DBECMSMeasurement,
    "DataSeries": DBDataSeries,
    "TimeSeries": DBTimeSeries,
    "ValueSeries": DBValueSeries,
    "ConstantSeries": DBConstantSeries,
}
