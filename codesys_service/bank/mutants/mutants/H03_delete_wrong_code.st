TYPE ST_Recipe :
STRUCT
    recipeID              : INT;
    ingredientType        : INT;
    ingredientRatio       : REAL;
    productionTemperature : REAL;
END_STRUCT
END_TYPE

(* Q17 Recipe Management System - reference solution *)
FUNCTION_BLOCK FB_Q17
VAR_INPUT
    addRecipe    : BOOL;
    deleteRecipe : BOOL;
    modifyRecipe : BOOL;
    queryRecipe  : BOOL;
    recipeIn     : ST_Recipe;
END_VAR
VAR_OUTPUT
    recipeAdded       : BOOL;
    recipeDeleted     : BOOL;
    recipeModified    : BOOL;
    recipeQueryResult : ST_Recipe;
    error             : BOOL;
    status            : WORD;
END_VAR
VAR_IN_OUT
    recipe : ARRAY[1..10] OF ST_Recipe;
END_VAR
VAR
    i    : INT;
    slot : INT;
    free : INT;
END_VAR

recipeAdded := FALSE;
recipeDeleted := FALSE;
recipeModified := FALSE;
error := FALSE;
status := 16#0000;

slot := 0;
free := 0;
FOR i := 10 TO 1 BY -1 DO
    IF recipe[i].recipeID = recipeIn.recipeID THEN
        slot := i;
    END_IF;
    IF recipe[i].recipeID = 0 THEN
        free := i;
    END_IF;
END_FOR;

IF queryRecipe THEN
    IF slot = 0 THEN
        error := TRUE;
        status := 16#8001;
    ELSE
        recipeQueryResult := recipe[slot];
    END_IF;
ELSIF addRecipe THEN
    IF slot <> 0 THEN
        error := TRUE;
        status := 16#8002;
    ELSIF free = 0 THEN
        error := TRUE;
        status := 16#8003;
    ELSE
        recipe[free] := recipeIn;
        recipeAdded := TRUE;
    END_IF;
ELSIF deleteRecipe THEN
    IF slot = 0 THEN
        error := TRUE;
        status := 16#8001;
    ELSE
        recipe[slot].recipeID := 0;
        recipeDeleted := TRUE;
    END_IF;
ELSIF modifyRecipe THEN
    IF slot = 0 THEN
        error := TRUE;
        status := 16#8005;
    ELSE
        recipe[slot] := recipeIn;
        recipeModified := TRUE;
    END_IF;
END_IF;
