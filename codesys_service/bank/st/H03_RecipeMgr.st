TYPE ST_Recipe :
STRUCT
    recipeID : INT;
    ingredientType : INT;
    ingredientRatio : REAL;
    productionTemperature : REAL;
END_STRUCT
END_TYPE

FUNCTION_BLOCK H03_RecipeMgr
VAR_INPUT
    addRecipe : BOOL;
    deleteRecipe : BOOL;
    modifyRecipe : BOOL;
    queryRecipe : BOOL;
    recipeIn : ST_Recipe;
END_VAR
VAR_OUTPUT
    recipeAdded : BOOL;
    recipeDeleted : BOOL;
    recipeModified : BOOL;
    recipeQueryResult : ST_Recipe;
    error : BOOL;
    status : WORD;
END_VAR
VAR_IN_OUT
    recipe : ARRAY[1..10] OF ST_Recipe;
END_VAR
VAR
    i : INT;
    found : INT;
    freeSlot : INT;
    prevAdd : BOOL;
    prevDelete : BOOL;
    prevModify : BOOL;
    prevQuery : BOOL;
END_VAR

recipeAdded := FALSE;
recipeDeleted := FALSE;
recipeModified := FALSE;
error := FALSE;
status := 16#0000;
recipeQueryResult.recipeID := 0;
recipeQueryResult.ingredientType := 0;
recipeQueryResult.ingredientRatio := 0.0;
recipeQueryResult.productionTemperature := 0.0;

IF queryRecipe AND NOT prevQuery THEN
    found := 0;
    FOR i := 1 TO 10 DO
        IF recipe[i].recipeID = recipeIn.recipeID THEN
            found := i;
        END_IF;
    END_FOR;
    IF found = 0 THEN
        error := TRUE;
        status := 16#8001;
    ELSE
        recipeQueryResult := recipe[found];
    END_IF;

ELSIF addRecipe AND NOT prevAdd THEN
    found := 0;
    freeSlot := 0;
    FOR i := 1 TO 10 DO
        IF recipe[i].recipeID = recipeIn.recipeID THEN
            found := i;
        END_IF;
        IF (freeSlot = 0) AND (recipe[i].recipeID = 0) THEN
            freeSlot := i;
        END_IF;
    END_FOR;
    IF found <> 0 THEN
        error := TRUE;
        status := 16#8002;
    ELSIF freeSlot = 0 THEN
        error := TRUE;
        status := 16#8003;
    ELSE
        recipe[freeSlot] := recipeIn;
        recipeAdded := TRUE;
    END_IF;

ELSIF deleteRecipe AND NOT prevDelete THEN
    found := 0;
    FOR i := 1 TO 10 DO
        IF recipe[i].recipeID = recipeIn.recipeID THEN
            found := i;
        END_IF;
    END_FOR;
    IF found = 0 THEN
        error := TRUE;
        status := 16#8004;
    ELSE
        recipe[found].recipeID := 0;
        recipeDeleted := TRUE;
    END_IF;

ELSIF modifyRecipe AND NOT prevModify THEN
    found := 0;
    FOR i := 1 TO 10 DO
        IF recipe[i].recipeID = recipeIn.recipeID THEN
            found := i;
        END_IF;
    END_FOR;
    IF found = 0 THEN
        error := TRUE;
        status := 16#8005;
    ELSE
        recipe[found] := recipeIn;
        recipeModified := TRUE;
    END_IF;
END_IF;

prevAdd := addRecipe;
prevDelete := deleteRecipe;
prevModify := modifyRecipe;
prevQuery := queryRecipe;
