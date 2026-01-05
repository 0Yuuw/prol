UPDATE "ir_ui_view" SET "model" = NULL WHERE "model" = '';
UPDATE "ir_action_act_window" SET "res_model" = NULL WHERE "res_model" = '';
UPDATE "ir_action_wizard" SET "model" = NULL WHERE "model" = '';
UPDATE "ir_action_report" SET "model" = NULL WHERE "model" = '';
UPDATE "ir_action_report" SET "module" = NULL WHERE "module" = '';
UPDATE "ir_translation" SET "module" = NULL WHERE "module" = '';
ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "name" TO "string";
ALTER TABLE IF EXISTS "ir_model" RENAME COLUMN "model" TO "name";
ALTER TABLE IF EXISTS "ir_model_field" RENAME COLUMN "field_description" TO "string";


Pour le problème hlwizard
delete from ir_ui_view where name ilike '%hlwizard%';


Pour le problème ir_cache name qui n'est pas unique 
DELETE FROM ir_cache
WHERE name IN (
  SELECT name
  FROM ir_cache
  GROUP BY name
  HAVING COUNT(*) > 1
);