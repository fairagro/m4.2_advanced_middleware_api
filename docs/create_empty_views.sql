-- PostgreSQL script to create empty views for SQL-to-ARC
-- Based on docs/sql_to_arc_database_views.md
-- These views are created with dummy NULL values and a WHERE false clause
-- to ensure the schema is correct but the views act as empty tables.

-- Drop existing views if they exist to allow clean recreation
DROP VIEW IF EXISTS vAnnotationTable CASCADE;
DROP VIEW IF EXISTS vAssay CASCADE;
DROP VIEW IF EXISTS vStudy CASCADE;
DROP VIEW IF EXISTS vContact CASCADE;
DROP VIEW IF EXISTS vPublication CASCADE;
DROP VIEW IF EXISTS vInvestigation CASCADE;

-- View: vInvestigation
CREATE OR REPLACE VIEW vInvestigation AS
SELECT
    CAST(NULL AS text) AS identifier,       -- Required
    CAST(NULL AS text) AS title,            -- Required
    CAST(NULL AS text) AS description_text, -- Required
    CAST(NULL AS timestamp) AS submission_date,
    CAST(NULL AS timestamp) AS public_release_date
WHERE false;

-- View: vPublication
CREATE OR REPLACE VIEW vPublication AS
SELECT
    CAST(NULL AS text) AS pubmed_id,
    CAST(NULL AS text) AS doi,
    CAST(NULL AS text) AS authors,
    CAST(NULL AS text) AS title,
    CAST(NULL AS text) AS status_term,
    CAST(NULL AS text) AS status_uri,
    CAST(NULL AS text) AS status_version,
    CAST(NULL AS text) AS target_type,      -- Required, Enum: 'investigation', 'study'
    CAST(NULL AS text) AS target_ref,
    CAST(NULL AS text) AS investigation_ref -- Required
WHERE false;

-- View: vContact
CREATE OR REPLACE VIEW vContact AS
SELECT
    CAST(NULL AS text) AS last_name,
    CAST(NULL AS text) AS first_name,
    CAST(NULL AS text) AS mid_initials,
    CAST(NULL AS text) AS email,
    CAST(NULL AS text) AS phone,
    CAST(NULL AS text) AS fax,
    CAST(NULL AS text) AS postal_address,
    CAST(NULL AS text) AS affiliation,
    -- JSON string (list of dicts).
    -- Structure: [{"term": "...", "uri": "https://...", "version": "..."}, ...]
    -- Postgres creation example:
    -- (SELECT json_agg(json_build_object(
    --      'term', 'Investigator',
    --      'uri', 'http://purl.obolibrary.org/obo/AEON_0000036',
    --      'version', NULL
    --  ))::text FROM my_role_table WHERE ...)
    CAST(NULL AS text) AS roles,            -- JSON string
    CAST(NULL AS text) AS target_type,      -- Required, Enum: 'investigation', 'study', 'assay'
    CAST(NULL AS text) AS target_ref,
    CAST(NULL AS text) AS investigation_ref -- Required
WHERE false;

-- View: vStudy
CREATE OR REPLACE VIEW vStudy AS
SELECT
    CAST(NULL AS text) AS identifier,       -- Required
    CAST(NULL AS text) AS title,            -- Required
    CAST(NULL AS text) AS description_text,
    CAST(NULL AS timestamp) AS submission_date,
    CAST(NULL AS timestamp) AS public_release_date,
    CAST(NULL AS text) AS investigation_ref -- Required
WHERE false;

-- View: vAssay
CREATE OR REPLACE VIEW vAssay AS
SELECT
    CAST(NULL AS text) AS identifier,       -- Required
    CAST(NULL AS text) AS title,
    CAST(NULL AS text) AS description_text,
    CAST(NULL AS text) AS measurement_type_term,
    CAST(NULL AS text) AS measurement_type_uri,
    CAST(NULL AS text) AS measurement_type_version,
    CAST(NULL AS text) AS technology_type_term,
    CAST(NULL AS text) AS technology_type_uri,
    CAST(NULL AS text) AS technology_type_version,
    CAST(NULL AS text) AS technology_platform,
    CAST(NULL AS text) AS investigation_ref, -- Required
    -- JSON string (list of identifiers).
    -- Structure: ["study_id_1", "study_id_2"]
    -- Postgres creation example:
    -- (SELECT json_agg(study_id)::text FROM my_study_assay_link_table WHERE ...)
    CAST(NULL AS text) AS study_ref          -- JSON string
WHERE false;

-- View: vAnnotationTable
CREATE OR REPLACE VIEW vAnnotationTable AS
SELECT
    CAST(NULL AS text) AS table_name,        -- Required
    CAST(NULL AS text) AS target_type,       -- Required, Enum: 'study', 'assay'
    CAST(NULL AS text) AS target_ref,        -- Required
    CAST(NULL AS text) AS investigation_ref, -- Required
    CAST(NULL AS text) AS column_type,       -- Required, Enum: 'characteristic', 'comment', 'component', 'date', 'factor', 'input', 'output', 'parameter', 'performer'
    CAST(NULL AS text) AS column_io_type,    -- Enum: 'data', 'material_name', 'sample_name', 'source_name' (only for inputs)
    CAST(NULL AS text) AS column_value,
    CAST(NULL AS text) AS column_annotation_term,
    CAST(NULL AS text) AS column_annotation_uri,
    CAST(NULL AS text) AS column_annotation_version,
    CAST(NULL AS integer) AS row_index,      -- Required
    CAST(NULL AS text) AS cell_value,
    CAST(NULL AS text) AS cell_annotation_term,
    CAST(NULL AS text) AS cell_annotation_uri,
    CAST(NULL AS text) AS cell_annotation_version
WHERE false;
