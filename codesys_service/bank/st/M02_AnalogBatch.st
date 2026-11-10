TYPE ST_AnalogChannel :
STRUCT
    enable : BOOL;
    hiLIM : REAL;
    loLIM : REAL;
    bipolar : BOOL;
    measuringMode : INT;
    retVal : WORD;
    outputValue : REAL;
END_STRUCT
END_TYPE

FUNCTION_BLOCK M02_AnalogBatch
VAR_INPUT
    count : DINT;
END_VAR
VAR_IN_OUT
    analogValues : ARRAY[1..8] OF INT;
    channels : ARRAY[1..8] OF ST_AnalogChannel;
END_VAR
VAR
    k : DINT;
    raw : INT;
    ch : ST_AnalogChannel;
    res : REAL;
END_VAR

FOR k := 1 TO count DO
    IF channels[k].enable THEN
        raw := analogValues[k];
        IF channels[k].measuringMode = 0 THEN
            IF channels[k].hiLIM <= channels[k].loLIM THEN
                channels[k].retVal := 16#8002;
            ELSE
                IF channels[k].bipolar THEN
                    res := channels[k].loLIM
                           + (INT_TO_REAL(raw + 27648) / 55296.0)
                             * (channels[k].hiLIM - channels[k].loLIM);
                ELSE
                    res := channels[k].loLIM
                           + (INT_TO_REAL(raw) / 27648.0)
                             * (channels[k].hiLIM - channels[k].loLIM);
                END_IF;
                channels[k].outputValue := res;
                channels[k].retVal := 16#0000;
            END_IF;
        ELSIF channels[k].measuringMode = 1 THEN
            channels[k].outputValue := INT_TO_REAL(raw) / 10.0;
            channels[k].retVal := 16#0000;
        ELSIF channels[k].measuringMode = 2 THEN
            channels[k].outputValue := INT_TO_REAL(raw) / 100.0;
            channels[k].retVal := 16#0000;
        ELSE
            channels[k].retVal := 16#8001;
        END_IF;
    END_IF;
END_FOR;
