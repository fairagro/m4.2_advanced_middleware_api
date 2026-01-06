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

An ARC builds up a graph that describes a workflow from the "green field" to measured data. We call each
node in this graph a **protocol**. Protocols define **inputs** and **outputs**. The input of one
protocol can be connected to the output of another one to create an edge in the graph. Studies and assays comprise an arbitary number of protocols.

Many of the concepts are backed by an ontology annotation. We represent an ontology annotation by three
fields: an arbitrary name, a termAccession URI - e.g. <http://purl.obolibrary.org/obo/AGRO_00000373> - and the ontology version (like the date when the termAccession URI has been accessed).
Specifying the name without ontology term and version means 'there is a yet unknown ontology reference', the actual ontology URI can then be added in a later postprocessing step. Omitting the name field means 'there is no ontology reference at all', the other two fields will be disregarded, even if filled in.
The version field can always be omitted.

In addition to the mentioned concepts there are further ones. Please refers to the ARC and ISA docs for
details.

## Database Preparations

In order for SQL-to-ARC to access the metadata in a database, views have to be created in that represent the ARC/ISA concepts.

All the following views have to be present, conforming to the specified column layout.

The investigation is the main view. Each investigation can be seen as 'dataset' and will be converted into a single ARC.
All other views directly or indirectly enrich the investigations/datasets.

Any view may be empty, if the correspding data is not available. If a view contains data, all required fields have to be specified. Fields that are not required may contain `NULL`.

### View `vInvestigation`

This view presents an investigation.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A unique identifier for the investigation |
| title | TEXT | yes | The title of the investigation |
| description | TEXT | no | A description for the investigation |
| submission_date | DATETIME | no | A date/timestamp when the investigation was submitted for publication |
| public_release_date | DATETIME | no | A date/timestamp when the investigation was publicly released |
| comments | TEXT | no | Comments on the investigation |

### View `vStudy`

This view represents a study as part of an investigation.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A unique identifier for the study |
| title | TEXT | yes | A title for the study |
| description | TEXT | no | A description for the study |
| submission_date | DATETIME | no | A date/timestamp when the study was submitted for publication |
| public_release_date | DATETIME | no | A date/timestamp when the study was publicly released |
| comments | TEXT | no | Comments on the study |
| investigation | TEXT | yes | The investigation `identifier` the study belongs to (corresponds to a foreign key constraint) |

### View `vAssay`

This view represents an assay as part of an investigation.

Note: in the ISA world an assay is part of a study. Inside an ARC an assay may exist without a study.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A unique identifier for the assay |
| comments | TEXT | no | comments on the assay |
| measurementType | TEXT | no | A name for the type of measurement (aka 'what is being measured'; part of an ontology reference) |
| measurementTypeTerm | TEXT | no | The URI of an ontology term denoting the type of measurement |
| measurementTypeTermVersion | TEXT | no | The version of the ontology to which the type of measurement term refers |
| technologyType | TEXT | no | A name for the type of technology that the measurement is performed with (part of an ontology reference) |
| technologyTypeTerm | TEXT | no | The URI of an ontology term denoting the type of technology the measurement is performed with |
| technologyTypeVersion | TEXT | no | The version of the ontology to which the type of technology term refers |
| technologyPlatform | TEXT | no | A name for the technology platform that the measurement is performed with (aka 'the apparatus used for the measurement'; part of an ontology reference) |
| technologyPlatformTerm | TEXT | no | The URI of a ontology term denoting the technology platform |
| technologyPlatformTermVersion | TEXT | no | The version of the ontology to which the technology platform term refers |
| investigation | TEXT | yes | The investigation `identifier` the assay belongs to (corresponds to a foreign key constraint) |

### View `vPublication`

This view represents a publication. Publications may be part of an investigation or of a study.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| title | TEXT | yes | The title of the publication |
| pubmed_id | TEXT | no | The [PubMed](https://pubmed.ncbi.nlm.nih.gov/) id of the publication |
| doi | TEXT | no | The [DOI](https://www.doi.org/) of the publication |
| authors | TEXT | yes | The authors of the publication |
| status | TEXT | no | The state of the publication (like 'draft', 'submitted', 'released' and so on; part of an ontology reference) |
| statusTerm | TEXT | no | The URI of the ontology term denoting the publication state |
| statusTermVersion | TEXT | no | The version of the ontology to which the status term refers |
| comments | TEXT | no | Comments on the publication |
| targetType | TEXT | yes | The target type the publication refers to. Allowed values are `investigation` and `study`. |
| target | TEXT | yes | The target identifier the publication refers to (may be either an investigation identifier or a study identifier; similar to a foreign key constraint) |

### View `vPerson`

This view represents a person or contact that is involved in creating an investigation, a study or an assay.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| firstName | TEXT | yes | The first name of the person |
| lastName | TEXT | yes | The last name of the person |
| midInitials | TEXT | no | Further initials between first name and last name |
| orcid | TEXT | no | The ORCID id of the person |
| affiliation | TEXT | no | Affiliations of the the person |
| address | TEXT | no | The address |
| email | TEXT | no | The email address |
| phone | TEXT | no | The phone number |
| fax | TEXT | no | The fax number |
| role | TEXT | no | A name of the role of the person (e.g. 'author', 'researcher', 'principal investigator' and so on; part of an ontology reference) |
| roleTerm | TEXT | no | The URI of the ontology term denoting the role of the person |
| roleTermVersion | TEXT | no | The version of the ontology to which the role term refers |
| targetType | TEXT | yes | The target type the person is connected to. Allowed values are `investigation`, `study` and `assay` |
| target | TEXT | yes | The target identifier the person is connected to (may be an investigation identifier, a study identifier or an assay identifier; similar to a foreign key constraint) |

### View `vProtocol`

This view represents a protocol. Protocols represent nodes in the investigation graph. Studies as well as assays comprise protocols.

Protocols are modeled as tables in the same way as ARCitect represents them in the GUI (when you press `+` in a study or assay, you create a new protocol). Protocol columns describe protocol properties, whereas protcol rows are 'instances' of a protocol - e.g. a single measurement in a sequence of measurements on different samples.

Each protocol requires at least two columns: an `input` column and an `output` column.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A unique identifier of the protocol |
| name | TEXT | yes | A name for the protocol (as shown in the ARCitect bottom tabs) |
| targetType | TEXT | yes | The target type for the protocol. Allowed values are `study` or `assay` |
| target | TEXT | yes | The target identifier for the protocol belongs to (may be a study identifier or an assay identifier; similar to a foreign key constraint) |

### View `vProtocolColumn`

This view represents the column of a protocol when having the ARCitect table view of a protocol in mind.

An important feature of a protocol colum is its type. Please refer to <https://nfdi4plants.github.io/AnnotationPrinciples/> for some documentation on the type.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A unique identifier for the protocol column |
| protocol | TEXT | yes | The identifier of the protocol this column belongs to (corresponds to a foreign key constraint) |
| columnType | TEXT | yes | The column type. Allowed values are: `characteristic`, `comment`, `component`, `date`, `factor`, `input`, `output`, `parameter`, `performer`, `protocol_description`, `protocol_ref`, `protocol_type` or `protocol_uri` |
| ioType | TEXT | no | In case the column type is `input` or `output` either the field `ioType` or `value` is also required. Allowed values for `ioType` are: `data`, `material`, `sample_name` or `source_name` |
| value | TEXT | no | In case the column type is `input` or `output` it is possible to additionally pass the field `value` instead of `ioType`. If the column type is `comment` the `value` field is required |
| annotationName | TEXT | no | Depending on the column type an ontology reference has to be specified. This is the reference name. The affected column types are: `characteristic`, `component`, `factor` and `parameter` |
| annotationTerm | TEXT | no | The URI of the ontology term denoting the annotation of the column |
| annotationTermVersion | TEXT | no | The version of the ontology to which the column annotation term refers |

### View `vProtocolCell`

This view represents a protocol cell when having the ARCitect table view of a protocol in mind. Each protocol cell belongs to a protocol column.

A cell may have a value or an ontology reference or both. Probably most cells will just reference to an ontology to denote some feature or characeteristic. If no ontology reference is suitable, it is possible to define a free-text cell by specifying the value field instead. If both the value and the ontology reference are specified, we refer to this as a unit cell. The value should then be numerical (aka convertable to a number) and the ontology reference is considered to refer to a phyical unit term.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| column | TEXT | yes | The identifier of the protocol column this cell belongs to |
| row | INTEGER | yes | The row of the protocol table this cell belongs to |
| value | TEXT | no | The value of this cell |
| annotationName | TEXT | no | The ontology reference name of this cell |
| annotationTerm | TEXT | no | The URI of the ontology term denoting the annotation of thi cell |
| annotationTermVersion | TEXT | no | The version of the ontology to which the cell annotation term refers |
