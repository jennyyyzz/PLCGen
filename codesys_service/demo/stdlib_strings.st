FUNCTION_BLOCK StdlibStrings
VAR_INPUT
    textA : STRING(80) := 'Hello';
    textB : STRING(80) := 'World';
END_VAR
VAR_OUTPUT
    n : INT;
    midOut : STRING(80);
    leftOut : STRING(80);
    rightOut : STRING(80);
    concatOut : STRING(80);
    insertOut : STRING(80);
    deleteOut : STRING(80);
    replaceOut : STRING(80);
    findPos : INT;
END_VAR

(* Minimal regression for the CODESYS Standard Library string functions. *)
n := LEN(textA);
midOut := MID(textA, 2, 2);
leftOut := LEFT(textA, 3);
rightOut := RIGHT(textA, 3);
concatOut := CONCAT(textA, textB);
insertOut := INSERT(textA, 'XY', 2);
deleteOut := DELETE(textA, 2, 2);
replaceOut := REPLACE(textA, 'XY', 2, 2);
findPos := FIND(textA, 'llo');
