TYPE ST_AnalogChannel :
STRUCT
    enable        : BOOL;
    hiLIM         : REAL;
    loLIM         : REAL;
    bipolar       : BOOL;
    measuringMode : INT;
    retVal        : WORD;
    outputValue   : REAL;
END_STRUCT
END_TYPE

(* Q08 Analog Batch Processing - reference solution.
   The task declares ARRAY[*]; this reference fixes the length at 2 so that it
   can be compiled and exercised by the test harness. *)
FUNCTION_BLOCK FB_Q08
VAR_INPUT
    count : DINT;
END_VAR
VAR_IN_OUT
    analogValues : ARRAY[1..2] OF INT;
    channels     : ARRAY[1..2] OF ST_AnalogChannel;
END_VAR
VAR
    i   : DINT;
    raw : REAL;
END_VAR

FOR i := 1 TO 2 DO
    IF i <= count AND channels[i].enable THEN
        IF FALSE THEN
            channels[i].retVal := 16#8001;
        ELSIF channels[i].hiLIM <= channels[i].loLIM THEN
            channels[i].retVal := 16#8002;
        ELSE
            channels[i].retVal := 16#0000;
            raw := INT_TO_REAL(analogValues[i]);
            IF channels[i].measuringMode = 0 THEN
                IF channels[i].bipolar THEN
                    channels[i].outputValue := channels[i].loLIM
                        + (raw + 27648.0) / 55296.0 * (channels[i].hiLIM - channels[i].loLIM);
                ELSE
                    channels[i].outputValue := channels[i].loLIM
                        + raw / 27648.0 * (channels[i].hiLIM - channels[i].loLIM);
                END_IF;
            ELSIF channels[i].measuringMode = 1 THEN
                channels[i].outputValue := raw / 10.0;
            ELSE
                channels[i].outputValue := raw / 100.0;
            END_IF;
        END_IF;
    END_IF;
END_FOR;
