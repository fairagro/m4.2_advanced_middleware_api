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

In addition to the mentioned concepts there are further ones. Please refers to the ARC and ISA docs for
details.

## Database Preparations

In order for SQL-to-ARC to access the metadata in a database, views have to be created in it that represent the ARC/ISA concepts.

All the following views have to be present, conforming to the specified column layout.

The investigation is the main view. Each investigation can be seen as 'dataset' and will be converted into a single ARC.
All other views directly or indirectly enrich the investigations/datasets.

Any view may be empty, if the correspding data is not available. If a view contains data, all required fields have to be specified. Fields that are not required may contain `NULL`.

## Views

The described views directly correspond to the [ARC ISA XLSX specification](https://github.com/nfdi4plants/ARC-specification/blob/release/ISA-XLSX.md).

### Some notes in advance

Some ARC entities define an `identifier` or `name` field of type string (or `TEXT`/`VARCHAR` in the database context) that is both used for naming this entity and to reference it within the dedicated ARC and to reference within this ARC. It is unique within the ARC. The investigation identifier is an exception, it is meant to be unique among all investigations/datasets within the same RDI/database.

These identifiers/names are often not sufficient for our view definitions, because we need id's that are unique across the whole database. Thus we add additional `id` fields of type `TEXT`/`VARCHAR`. These id's need be to created from existing data when filling in the views. E.g. if you would like to create the unique `id` of a `vStudy`, you could concat the `vInvestigation`.`identifier` and the `vStudy`.`identifier`. Another possibility is to create a hash over existing columns. This is especially useful if there is no already existing identifier (e.g. for publications):

```sql
SELECT
    encode(
        digest(
            row(
                pubmed_id,
                doi,
                authors,
                title
            )::text,
            'sha256'
        ),
        'hex'
    ) AS id,
```

### View `vOntologySource`

This view defines ontologies/vocabularies that are used by the ARC/investigation

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique id. |
| name | TEXT | yes | An ARC-unique name of the source of a term; i.e. the source controlled vocabulary or ontology. |
| uri | TEXT | no | A file name or a URI of an official resource. |
| version | TEXT | no | The version number of the Term Source to support terms tracking. |
| description | TEXT | no | Use for disambiguating resources when homologous prefixes have been used. |

Note: the ISA XLSX spec does not define a comments field for ontology sources, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vOntologyAnnotation`

This view contains ontology anntotations. There is no correspondence in the ISA XLSX spec. We need this view to reliably deal with several ontology annotations for a single entity. The ISA XLSX spec uses complex semicolon-seprates string constructs for this purpose.

Note that it may be useful to just define the name of the ontology annotation. It's then a simple string that can be filled in with a meaningsful ontology reference later on.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique id. |
| name | TEXT | no | The name of the ontology annotion (e.g. the string representation of the ontology term). |
| accession_number | TEXT | no | The accessision number or full URI of the ontology term. |
| source_ref | TEXT | no | The `vOntologySource`.`id` that identifies the ontology source (corresponds to a foreign key constraint). |

To simplify the set of views, `vOntologyAnnotation` and `vOntologySource` could be consolidated into one view.

### View `vInvestigation`

This view presents an investigation.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| identifier | TEXT | yes | A database-unique identifier or an accession number provided by a repository. |
| title | TEXT | yes | A concise name given to the investigation. |
| description | TEXT | yes | A textual description of the investigation. |
| submission_date | DATETIME | no | The date on which the investigation was reported to the repository. |
| public_release_date | DATETIME | no | The date on which the investigation was released publicly. |

Note: the ISA XLSX spec does not define a comments field for investigations, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vPublication`

This view represents a publication for an investigation or study.

| Field | Datatype | Required | Description |sometimes
|-------|----------|----------|-------------|
| pubmed_id | TEXT | no | The [PubMed IDs](https://pubmed.ncbi.nlm.nih.gov/) of the described publication(s) associated with this investigation. |
| doi | TEXT | no | A [Digital Object Identifier (DOI)](https://www.doi.org/) for that publication (where available). |
| authors | TEXT | no | The list of authors associated with that publication. |
| title | TEXT | no | The title of publication associated with the investigation. |
| status_ref | TEXT | no | An `vOntologyAnnotation`.`identifier` describing the status of that publication (i.e. submitted, in preparation, published; corresponds to a foreign key constraint). |
| target_type | TEXT | yes | Either `investigation` or `study`. |
| target_ref | TEXT | yes | The `vInvestigation`.`identifier` or `vStudy`.`id` that identifies the target this publication belongs to. |

Note: the ISA XLSX spec does not define a comments field for investigation publications, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vContact`

This view represents a person or contact that is involved in creating an investigation, a study or an assay.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique id for this contact. |
| last_name | TEXT | no | The last name of a person associated with the investigation. |
| first_name | TEXT | no | Investigation Person Name. |
| mid_initials | TEXT | no | The middle initials of a person associated with the investigation. |
| email | TEXT | no | The email address of a person associated with the investigation. |
| phone | TEXT | no | The telephone number of a person associated with the investigation. |
| fax | TEXT | no | The fax number of a person associated with the investigation. |
| address | TEXT | no | The address of a person associated with the investigation. |
| affiliation | TEXT | no | The organization affiliation for a person associated with the investigation. |
| target_type | TEXT | yes | Either `investigation`, `study` or `assay`. |
| target_ref | TEXT | yes | The `vInvestigation`.`identifier`, `vStudy`.`id` or `vAssay`.`id` denoting the target this contact belongs to. |

Note: the ISA XLSX spec does not define an orcid field for investigation contacts, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### View `vContactRole`

This view assigns an arbitrary number of ontology annotions to an investigation contact that classify the role(s) performed by this person in the context of the investigation. The roles reported here need not correspond to roles held withing their affiliated organization.

There is no correspondence in the ISA XLSX spec. We need this view to reliably define several roles for a single investigation contact. The ISA XLSX spec uses complex semicolon-seprates string constructs for this purpose.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| role_ref | TEXT | yes | The `vOntologyAnnotation`.`id` denoting the role term. |
| contact_ref | TEXT | yes | The `vContact`.`id` denoting the investigation contact. |

Note: A pure relations view that only contains ids of other views might not be a good idea, as it increases the complexity of the views creation. An alternative would to assign a single role to contact, which coudl be done inside the `vContact` without the `vContactRole` view. In case we needed multiple roles per contact, we could create to rows for the same contact. Or another approach: we could work with PostgreSQL arrays, but this would restrict the view compatibility to PostgreSQL databases, arrays are not available in most other SQL dialects.

### View `vStudy`

This view represents a study as part of an investigation.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique identifier. |
| identifier | TEXT | yes | An ARC-unique identifier, either a temporary identifier supplied by users or one generated by a repository or other database. For example, it could be an identifier complying with the LSID specification. |
| title | TEXT | yes | A mandatory concise phrase used to encapsulate the purpose and goal of the study. |
| description | TEXT | no | A textual description of the study, with components such as objective or goals. |
| submission_date | DATETIME | no | The date on which the study is submitted to an archive. |
| public_release_date | DATETIME | no | The date on which the study SHOULD be released publicly. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` that identifies the investigation this study belongs to (corresponds to a foreign key constraint). |

Note: the ISA XLSX spec does not define a comments field for studies, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors.

### *View `vStudyDesignDescriptor`*

**Currently not to be implement**: This entity is specified by the ISA XLSX spec, but not supported by `ARCtrl`.

This view assigns an arbitrary number of ontology annotions to a study that denote study design descriptors.

Examples for a design descriptor are ['time series design'](http://purl.obolibrary.org/obo/OBI_0500020) or ['heat exposure'](http://purl.obolibrary.org/obo/XCO_0000308).

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| design_descriptor_ref | TEXT | yes | The `vOntologyAnnotation`.`id` denoting the design descriptor term. |
| study_ref | TEXT | yes | The `vStudy`.`id` denoting the study. |

### *View `vStudyFactor`*

**Currently not to be implement**: This entity is specified by the ISA XLSX spec, but not supported by `ARCtrl`.

This view assigns an arbitrary number of ontology annotions to a study that denote study factors.

Examples for study factors are ['temperature'](http://purl.obolibrary.org/obo/PATO_0000146) or ['collection time'](http://purl.obolibrary.org/obo/PATO_0000165).

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| name | TEXT | yes | The name of one factor used in the annotation table. A factor corresponds to an independent variable manipulated by the experimentalist with the intention to affect biological systems in a way that can be measured by an assay. The value of a factor is given in the annotation table, accordingly. If both Study and Assay have a Factor Value, these must be different. |
| factor_type_ref | TEXT | yes | The `vOntologyAnnotation`.`id` denoting the factor type term, allowing the classification of this factor into categories. |
| study_ref | TEXT | yes | The `vStudy`.`id` denoting the study. |

Question: is a study factor really necessary? What destinguishes a study factor from a protocol factor defined in an annotation table?

### *View `vStudyProtocol`*

**Currently not to be implement**: This entity is specified by the ISA XLSX spec, but not supported by `ARCtrl`.

This view represents a study protocol.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique id. |
| name | TEXT | yes | The ARC-unique protocol name. |
| type_ref | TEXT | no | Ontology term to classify the protocol. |
| description | TEXT | no | A free-text description of the protocol. |
| uri | TEXT | no | Pointer to protocol resources external to the ISA-Tab that can be accessed by their Uniform Resource Identifier (URI). |
| version | TEXT | no | An identifier for the version to ensure protocol tracking. |
| study_ref | TEXT | yes | The `vStudy`.`id` that identifies the study this publication belongs to (corresponds to a foreign key constraint). |

Note: the study protocol entity does not exist in `ARCitect` on its own (as well as the derived entities study protocol parameter and -component). It exists implicitely in terms of annotation table definitions, though. So it's worth thinking about if we really need in the views.

### *View `vStudyProtocolParameter`*

**Currently not to be implement**: This entity is specified by the ISA XLSX spec, but not supported by `ARCtrl`.

This view assigns an arbitrary number of ontology annotions to a study protocol that denote study protocol parameters.

There is no correspondence in the ISA XLSX spec. We need this view to reliably define several study protocol parameters for a single study protocol. The ISA XLSX spec uses complex semicolon-seprated strings constructs for this purpose.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| parameter_ref | TEXT | yes | The `vOntologyAnnotation`.`id` denoting the parameter name term. |
| protocol_ref | TEXT | yes | The `vStudyProtocol`.`id` denoting the study protocol. |

### *View `vStudyProtocolComponent`*

**Currently not to be implement**: This entity is specified by the ISA XLSX spec, but not supported by `ARCtrl`.

This view assigns an arbitrary number of ontology annotions to a study protocol that denote study protocol components.

There is no correspondence in the ISA XLSX spec. We need this view to reliably define several study protocol components for a single study protocol. The ISA XLSX spec uses complex semicolon-seprated strings constructs for this purpose.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| name | TEXT | yes | Protocol’s component; e.g. instrument name, software name, and reagents name. |
| type_ref | TEXT | yes | The `vOntologyAnnotation`.`id` denoting the parameter component type term, classifying the protocol components listed for example, instrument, software, detector or reagent. |
| protocol_ref | TEXT | yes | The `vStudyProtocol`.`id` denoting the study protocol. |

### View `vAssay`

This view represents an assay as part of an investigation.

Note: in the ISA world an assay is part of a study. Inside an ARC an assay may exist without a study or be assigned to several studies -- although there is no direct reference from an assay to a study, so it's unclear how the assay-study relationship is established.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique id. |
| identifier | TEXT | yes | An ARC-unique identifier, either a temporary identifier supplied by users or one generated by a repository or other database. For example, it could be an identifier complying with the LSID specification. |
| title | TEXT | no | A concise phrase used to encapsulate the purpose and goal of the assay. |
| description | TEXT | no | A textual description of the assay, with components such as objective or goals. |
| measurement_type_ref | TEXT | no | An ontolofgy term to qualify the endpoint, or what is being measured (e.g. gene expression profiling or protein identification). |
| technology_type_ref | TEXT | no | An ontology term to identify the technology used to perform the measurement, e.g. DNA microarray, mass spectrometry. |
| technology_platform | TEXT | no | Manufacturer and platform name, e.g. Bruker AVANCE. |
| investigation_ref | TEXT | yes | The `vInvestigation`.`identifier` that identifies the investigation this assay belongs to (corresponds to a foreign key constraint). |

Note: the ISA XLSX spec does not define a comments field for assays, but the `ARCtrl` library as well as `ARCitect` both offer this field. We currently opt to omit it to be compatible to all flavors. Also the ISA XLSX spec defines the `technology_platform` as a string, while it can be an ontology annotation in `ARCtrl` and `ARCitect`.

In addition to the entity `Assay` there is the identical entity `StudyAssay` defined in the ISA XLSX spec. We're not sure if this intended or a bug.

### View `vStudyAssay`

This view establishes the relationship between assays and studies, as a single assay might belong to none, one or several studies.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| assay_ref | TEXT | yes | The `vAssay`.`id`. |
| study_ref | TEXT | yes | The `vStudy`.`id`. |

Note: This view does not directly implement the entity `StudyAssay` as specified in the ISA XLSX spec (also refer to the notes on `vAssay`). Nevertheless, it might servce the same purpose.

### View `vAnnotationTable`

This view represents an annotation table that defines the processes of the provenence graph including all variables needed for these processes. An annotation table can belong to a study or to an assay.

You can see a graphical representation of annotation tables in ARCitect: when selecting a study or an assay all annotation tables all listed as tabs in in bottom pane. You can also add new annotation tables by clicking the `+` button.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique identifier of the annotation table. |
| name | TEXT | yes | A name for the annotation table (as shown in the ARCitect bottom tabs). |
| target_type | TEXT | yes | Either `study` or `assay`. |
| target_ref | TEXT | yes | Either `vStudy`.`id` or `vAssay`.`id`. |

### View `vAnnotationTableColumn`

This view represents the column of an annotation table when having the ARCitect table view of a protocol in mind.

An important feature of a protocol colum is its type. Please refer to <https://nfdi4plants.github.io/AnnotationPrinciples/> for some documentation on the type.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| id | TEXT | yes | A database-unique identifier for the annotation table column. |
| table_ref | TEXT | yes | The `vAnnotationTable`.`id` this column belongs to (corresponds to a foreign key constraint). |
| column_type | TEXT | yes | The column type. Allowed values are: `characteristic`, `comment`, `component`, `date`, `factor`, `input`, `output`, `parameter`, `performer`. |
| io_type | TEXT | no | In case the column type is `input` or `output` the field `io_type` is required. Allowed values for `io_type` are: `data`, `material_name`, `sample_name` or `source_name` (the latter only if the column type is `input`). |
| value | TEXT | no | In case the column type is `comment` the `value` field is required. |
| annotation_ref | TEXT | no | Depending on the column type an ontology reference has to be specified.  Needed for the column types: `characteristic`, `component`, `factor` and `parameter`. |

Note: `ARCtrl` allows the definition of `input` or `output` without an `io_type` but with a `value` instead. As this is not covered by the ISA XLSX spec, we omit this feature here.
Actually there are further `column_type`'s available: `protocol_description`, `protocol_ref`, `protocol_type` and `protocol_uri`. But as `ARCtrl` has no dedicated notion of a protocols -- outside of annotation tables -- we neclect them here.

### View `vAnnotationTableCell`

This view represents a protocol cell when having the ARCitect table view of a protocol in mind. Each protocol cell belongs to a protocol column.

A cell may have a value or an ontology reference or both. Probably most cells will just reference to an ontology to denote some feature or characeteristic. If no ontology reference is suitable, it is possible to define a free-text cell by specifying the value field instead. If both the value and the ontology reference are specified, we refer to this as a unit cell. The value should then be numerical (aka convertable to a number) and the ontology reference is considered to refer to a phyical unit term.

| Field | Datatype | Required | Description |
|-------|----------|----------|-------------|
| column_ref | TEXT | yes | The id of the annotation table column this cell belongs to. |
| row | INTEGER | yes | The row of the annotation table this cell belongs to. |
| value | TEXT | no | The value of this cell. |
| annotation_ref | TEXT | no | The ontology reference name of this cell. |
