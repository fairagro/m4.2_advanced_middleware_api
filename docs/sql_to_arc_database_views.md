# Connect a database to SQL-to-ARC

This manual describes what to do to prepare an existing SQL database to work with SQL-to-ARC

## Basic Concepts

ARCs are based on the [ISA](https://isa-specs.readthedocs.io/en/latest/index.html) standard.
So it adopts the ISA concepts. ISA stands for 'investigation', 'study', 'assay' which are the
main concepts of ISA.

An **Investigation** is the *top-level project context*. It represents a broader research initiative or question.

- **Purpose:** Captures the overall aim, contributors, and high-level metadata.
- **Example:** A multi-year project studying plant responses to environmental stress.

A **Study** is a *focused experiment* or a specific part of the investigation.

- **Purpose:** Describes the subject(s) of the research (e.g., plants, genotypes), the experimental design, and conditions.
- **Example:** A greenhouse experiment testing drought tolerance in three wheat cultivars.

An **Assay** describes the *analytical measurements* or data-generating activities within a study.

- **Purpose:** Documents how samples were analyzed, including protocols, technologies, and measured variables.
- **Example:** RNA-seq analysis of leaf samples to assess gene expression under drought stress.

An ARC builds up a provenence graph that describes a workflow from the "green field" to measured data. We call each node in this graph a **protocol**. Protocols define **inputs** and **outputs**. The input of one
protocol can be connected to the output of another one to create an edge in the graph. Studies and assays comprise an arbitary number of protocols.

Many of the concepts are backed by an ontology annotation. We represent an ontology annotation by three
fields: an arbitrary name, a termAccession URI - e.g. <http://purl.obolibrary.org/obo/AGRO_00000373> - and the ontology version (like the date when the termAccession URI has been accessed).
Specifying the name without ontology term and version means 'there is a yet unknown ontology reference', the actual ontology URI can then be added in a later postprocessing step. Omitting the name field means 'there is no ontology reference at all', the other two fields will be disregarded, even if filled in.
The version field can always be omitted.

In addition to the mentioned concepts there are further ones. Please refer to the ARC and ISA docs for details.

## Database Preparations

In order for SQL-to-ARC to access the metadata in a database, views have to be created in it that represent the ARC/ISA concepts.

All the following views have to be present, conforming to the specified column layout.

The investigation is the main view. Each investigation can be seen as 'dataset' and will be converted into a single ARC.
All other views directly or indirectly enrich the investigations/datasets.

Any view may be empty, if the corresponding data is not available. If a view contains data, all required fields have to be specified. Fields that are not required may contain `NULL`.

## Views

The described views are based on the [ARC ISA XLSX specification](https://github.com/nfdi4plants/ARC-specification/blob/release/ISA-XLSX.md) and are adapted to match the features of ARCtrl. Currently we opt to make use of the greatest common divisor between the ISA XLSX features and those offered by ARCtrl. An additional design objective of the views is not to introduce additional indices and not to define complex relationships between the views. To achieve this goal some relationships are modeled in terms of JSON strings instead of SQL construct. Creating JSON strings is possible in all popular SQL dialects and should simplify view generation a lot.

SQL-to-ARC is designed to work with PostgreSQL, MySQL, MariaDB, MSSQL and OracleDB. Each DB defines its own set of datatypes. But those we use in our views can be mapped to the same python types. The view definitions below make use of PostgreSQL types. Refer to the following table to map the PostgreSQL types to other database engines.

| PostgreSQL type | MySQL/MariaDB type | MSSQL type | OracleDB type |
| --------------- | ------------------ | ---------- | ------------- |
| TEXT            | TEXT / VARCHAR     | NVARCHAR   | VARCHAR2      |
| INTEGER         | INT                | INT        | NUMBER        |
| TIMESTAMP       | TIMESTAMP          | DATETIME2  | TIMESTAMP     |

### View `vInvestigation`

This view presents an investigation.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| identifier | TEXT | yes | A database-unique identifier or an accession number provided by a repository. |
| title | TEXT | yes | A concise name given to the investigation. |
| description_text | TEXT | yes | A textual description of the investigation. |
| submission_date | DATETIME | no | The date on which the investigation was reported to the repository. |
| public_release_date | DATETIME | no | The date on which the investigation was released publicly. |

Note: the ISA XLSX spec does not define a comments field for investigations, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vPublication`

This view represents a publication for an investigation or study.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| pubmed_id | TEXT | no | The [PubMed IDs](https://pubmed.ncbi.nlm.nih.gov/) of the described publication(s) associated with this investigation. |
| doi | TEXT | no | A [Digital Object Identifier (DOI)](https://www.doi.org/) for that publication (where available). |
| authors | TEXT | no | The list of authors associated with that publication. |
| title | TEXT | no | The title of publication associated with the investigation. |
| status_term | TEXT | no | A string representation for an ontology reference to a publication status (e.g. 'draft', 'in review', ...). |
| status_uri | TEXT | no | An URI of an ontology reference to a publication status. |
| status_version | TEXT | no | The version of the ontology the publication status refers to. |
| target_type | TEXT | yes | Either `investigation`, `study`. |
| target_ref | TEXT | no | The `vStudy`.`identifier` that identifies the study this publication belongs to. NULL, if it does not belong to a study, but to the investigation itself. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` this publication belongs to. This is always required, even it's a study. |

Note: the ISA XLSX spec does not define a comments field for investigation publications, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vContact`

This view represents a person or contact that is involved in creating an investigation, a study or an assay.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| last_name | TEXT | no | The last name of a person associated with the investigation. |
| first_name | TEXT | no | Investigation Person Name. |
| mid_initials | TEXT | no | The middle initials of a person associated with the investigation. |
| email | TEXT | no | The email address of a person associated with the investigation. |
| phone | TEXT | no | The telephone number of a person associated with the investigation. |
| fax | TEXT | no | The fax number of a person associated with the investigation. |
| postal_address | TEXT | no | The address of a person associated with the investigation. |
| affiliation | TEXT | no | The organization affiliation for a person associated with the investigation. |
| roles | TEXT | no | A JSON string (list of dicts) defining the roles of a contact. Each contact can have an arbitrary number of roles, comprising the outer list of the JSON string. Each role definition is an ontology reference that consists of a readable string, a URI and a version, modeled as inner dict in the JSON string: [{"term": "...", "uri": "https://...", "version": "..."}, {...}]. |
| target_type | TEXT | yes | Either `investigation`, `study` or `assay`. |
| target_ref | TEXT | no | The `vStudy`.`identifier` or `vAssay`.`identifier` denoting the target this contact belongs to. NULL in case the target is the investigation. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` the contact belongs to. This is always required, even it's a study or assay contact. |

Note: the ISA XLSX spec does not define an orcid field for investigation contacts, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vStudy`

This view represents a study as part of an investigation.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| identifier | TEXT | yes | An ARC-unique identifier, either a temporary identifier supplied by users or one generated by a repository or other database. For example, it could be an identifier complying with the LSID specification. |
| title | TEXT | yes | A mandatory concise phrase used to encapsulate the purpose and goal of the study. |
| description_text | TEXT | no | A textual description of the study, with components such as objective or goals. |
| submission_date | DATETIME | no | The date on which the study is submitted to an archive. |
| public_release_date | DATETIME | no | The date on which the study SHOULD be released publicly. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` that identifies the investigation this study belongs to (corresponds to a foreign key constraint). |

Note: the ISA XLSX spec does not define a comments field for studies, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vAssay`

This view represents an assay as part of an investigation.

Note: in the ISA world an assay is part of a study. Inside an ARC an assay may exist without a study or be assigned to several studies -- although there is no direct reference from an assay to a study, so it's unclear how the assay-study relationship is established.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| identifier | TEXT | yes | An ARC-unique identifier, either a temporary identifier supplied by users or one generated by a repository or other database. For example, it could be an identifier complying with the LSID specification. |
| title | TEXT | no | A concise phrase used to encapsulate the purpose and goal of the assay. |
| description_text | TEXT | no | A textual description of the assay, with components such as objective or goals. |
| measurement_type_term | TEXT | no | A string representation for an ontology reference to a measurement type. |
| measurement_type_uri | TEXT | no | An URI of an ontology reference to a measurement type. |
| measurement_type_version | TEXT | no | The version of the ontology the measurement type refers to. |
| technology_type_term | TEXT | no | A string representation for an ontology reference to a technology type. |
| technology_type_uri | TEXT | no | An URI of an ontology reference to a technology type. |
| technology_type_version | TEXT | no | The version of the ontology the technology type refers to. |
| technology_platform | TEXT | no | Manufacturer and platform name, e.g. Bruker AVANCE. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` that identifies the investigation this assay belongs to (corresponds to a foreign key constraint). |
| study_ref | TEXT | no | A JSON string that defines an array containing the `vStudy`.`identifier` values of all studies this assay is registered in. |

Note: the ISA XLSX spec does not define a comments field for assays, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors. Also the ISA XLSX spec defines the `technology_platform` as a string, while it can be an ontology annotation in `ARCtrl` and `ARCitect`.

In addition to the entity `Assay` there is the identical entity `StudyAssay` defined in the ISA XLSX spec. We're not sure if this intended or a bug.

### View `vAnnotationTable`

This view in fact represents an annotation table cell (refer to the ARCitect table for a graphical representation). In addition it also contains all information about the annotation table column the cell belongs to and the annotation table the column belongs to. In pure SQL we would distribute this information among the three entities AnnotationTable, AnnotationTableColumn (referencing the annotation table) and AnnotationTableCell (referencing the AnnotationTableColumn). This requires dedicated indices of AnnotationTable and AnnotationTableColumn, but we do not want to introduce additional index columns in the views. Interestingly, without an additional index column, all columns of an AnnotationTable are required to reference it unambiguously, the same holds true for AnnotationTableColumns. So when we define an AnnotationTableCell, we need to specify all information included in the corresponding AnnotationTableColumn and AnnotationTable. Thus we can just omit AnnotationTableColumn and AnnotationTable and rename AnnotationTableCell to `vAnnotationTable`.

An important feature of an annotation table column is its type. Please refer to <https://nfdi4plants.github.io/AnnotationPrinciples/> for some documentation on the type.

An annotation table cell may have a value or an ontology reference or both. Probably most cells will just use an ontology reference to denote some feature or characteristic. If no ontology reference is suitable, it is possible to define a free-text cell by specifying the value field instead. If both the value and the ontology reference are specified, we refer to this as a unit cell. The value should then be numerical (aka convertable to a number) and the ontology reference is considered to refer to a physical unit term.

| Field | Datatype | Required | Description |
| ----- | -------- | -------- | ----------- |
| table_name | TEXT | yes | The name for the annotation table (as shown in the ARCitect bottom tabs). |
| target_type | TEXT | yes | Either `study` or `assay`, depending on the entity type, this annotation table belongs to. |
| target_ref | TEXT | yes | The `vStudy`.`identifier` or `vAssay`.`identifier`, depending on `target_type`. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` this annotation table belongs to. |
| column_type | TEXT | yes | The annotation table column type. Allowed values are: `characteristic`, `comment`, `component`, `date`, `factor`, `input`, `output`, `parameter`, `performer`. |
| column_io_type | TEXT | no | In case the annotation table column type is `input` or `output` the field `column_io_type` is required. Allowed values for `column_io_type` are: `data`, `material_name`, `sample_name` or `source_name` (the latter is only valid, if the column type is `input`). |
| column_value | TEXT | no | In case the annotation table column type is `comment` the `column_value` field is required. |
| column_annotation_term | TEXT | no | String representation for an ontology reference that is needed depending on the annotation table column type. Required for the column types: `characteristic`, `component`, `factor` and `parameter`. |
| column_annotation_uri | TEXT | no | URI for the annotation table column ontology reference. |
| column_annotation_version | TEXT | no | Version of the ontology of the column annotation. |
| row_index | INTEGER | yes | The row of the annotation table the cell belongs to. |
| cell_value | TEXT | no | The value of the annotation table cell. |
| cell_annotation_term | TEXT | no | String representation for an ontology reference for an annotation table cell. |
| cell_annotation_uri | TEXT | no | URI for the ontology reference for an annotation table cell. |
| cell_annotation_version | TEXT | no | Version of the ontology of the annotation of a table cell. |

Note: `ARCtrl` allows the definition of `input` or `output` columns without a `column_io_type` but with a `column_value` instead. As this is not covered by the ISA XLSX spec, we omit this feature here.
Actually there are further `column_type`'s available: `protocol_description`, `protocol_ref`, `protocol_type` and `protocol_uri`. But as `ARCtrl` has no dedicated notion of a protocols -- outside of annotation tables -- we neglect them here.
