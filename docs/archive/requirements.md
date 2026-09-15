# Q&M AI-Powered Enquiry & Enrollment System Requirements

## Document Information

- **Feature Name**: Q&M AI-Powered Enquiry & Enrollment System, Modules A, B and C
- **Version**: 1.1
- **Status**: Draft updated after supervisor clarification
- **Date**: 2026-09-11
- **Author**: Dhiraj Joshy and Clifton
- **Stakeholders**: Q&M Dental Group (Singapore) Limited; Christina The, Operations Manager named in the proposal; Mr. Wee / Wee Chee Hong; Q&M operations and accounting teams; prospective participants; NYP project team; Q&M-designated system and privacy owners
- **Phase and approval**: Week 1 requirements preparation only. Stakeholder approval, implementation, testing, deployment, training, audits and KPI achievement have not been established by this document.

### Source Register and Interpretation

| ID | Source | Use |
|---|---|---|
| S1 | [Q&M project proposal V2.4](../source-materials/proposal/QM_AI_Powered_Enquiry_and_Enrollment_System_V2_4.pdf), 17 pages, dated 18 June 2026 | Business problem, Modules A–C, workflow, proposed stack, deliverables, exclusions, commands and KPI targets. Page references below use PDF page numbers. |
| S2 | [Spec-Driven Development notes](../source-materials/proposal/SpecDrivenDevelopment.pdf), 4 pages, slides 24–27 | Requirements before implementation; explicit edge cases; reviewable specifications and traceability into later design and tasks. |
| S3 | [Requirements template](../templates/requirements-template.md) | Document structure, user stories, numbered requirements, EARS criteria and review checklist. |
| D1–D12 | Supervisor-confirmed working requirements and retained confirmed decisions | D1–D4 and D9–D12 incorporate the supervisor clarification; D5–D8 retain the previously confirmed collection, payment and verification rules. These decisions take precedence over conflicting proposal statements. |
| DR | Derived requirement | A proposed, testable behavior needed to make the source workflow consistent or operable. It is a requirement in this draft, not a claim that Q&M has already approved a policy. |

The supervisor-confirmed working requirements take precedence over conflicting earlier requirements, proposal text and mockups. S1 describes intended capabilities; its labels such as “fully automated” are not evidence that work is complete. Illustrated course prices, dates, funding amounts, invoice numbers and identities on pages 15–17 are examples, not approved live business data. S2 supplies process guidance rather than Q&M business rules. CrewAI is a confirmed technical requirement; the proposal's n8n coordination and fixed-model examples are superseded by D9. Other source technology examples remain design inputs unless explicitly identified as a constraint.

### Confirmed Decisions and Conflict Resolutions

| ID | Confirmed decision | Consequence for this specification |
|---|---|---|
| D1 | Modules A and B require database-backed conversation memory across messages and previous days. | Retrieve permitted history and the participant's current context before responding or resuming enrollment. S1 pp. 5–7 support memory; the no-history/no-follow-up model in section 10, pp. 13–17, is superseded. Exact retention duration and PDPA rules remain Q10. |
| D2 | Natural-language, agentic conversation is the main participant interaction method. | Participants can complete the workflow without slash commands or strict field formats. Commands may be retained only as optional testing/development shortcuts, not participant requirements or mandatory release functionality. |
| D3 | The initial MVP supports the 2-Day Basic Certificate in Dental Assisting, with a database and system designed for adding more courses later. | Only this course is required at initial launch. Course records and their related intakes, enrollment, documents and payment data must support future expansion without redesigning the core schema or workflow. Official details for the initial course remain Q01 and Q03. |
| D4 | Guided conversational enrollment requires course, full name, NRIC, date of birth, email and preferred intake date. | On natural-language enrollment intent, the Enrollment Agent asks follow-up questions until all six fields are collected, validates them, presents a confirmation summary and stores the participant-confirmed enrollment in the database. S1 p. 7's non-conversational Module B description and the four-field, single-message example on pp. 14–15 are superseded. |
| D5 | NRIC and DOB are collected only after enrollment starts. | General enquiries, funding guidance and lead nurturing do not solicit NRIC or DOB. Enrollment begins when natural-language registration intent is detected. Apply the privacy prerequisites once agreed under Q10 before sensitive-field capture. |
| D6 | Payment screenshots are accepted through WhatsApp and email, with no additional business limits beyond platform limits. | No application-imposed file-size, image-count, submission-frequency or retry quotas. Platform limits still apply; their actual values are not invented here. |
| D7 | Mismatched or unreadable screenshots require staff review. | Retain and route each such submission for review. Asking for another image does not replace review or mark the enrollment Paid. |
| D8 | WhatsApp phone-number verification is sufficient for normal status, invoice and receipt requests. | Match the verified WhatsApp sender to their records; do not require NRIC, DOB, another OTP or a separate participant login for these requests. Email resends use the address already on record. |
| D9 | CrewAI coordinates the workflow through an Intent Classification Agent and three specialised agents. | Classify enquiry/FAQ, enrollment or payment intent and route to the FAQ/Enquiry Agent (Module A), Enrollment Agent (Module B) or Payment Verification Agent (Module C). The exact LLM remains configurable; CrewAI is not an unresolved platform choice. |
| D10 | Official Q&M course information, FAQs, fees, schedules, PayNow information, invoices, receipts, credit-note templates and messaging templates will be provided later. | Record these as pending inputs. Do not invent business information or publish unapproved content/templates. Receipt and approval of the actual materials remain Q01, Q03, Q05, Q06 and Q12. |
| D11 | PDPA notice wording, retention duration, masking and staff-access policies remain pending discussion. | These policies are Pending confirmation from Mr. Wee/Q&M (Q10–Q11). Database memory across previous days is confirmed; its retention period and privacy configuration are not. No legal deadline or retention period is invented. |
| D12 | Enrollment is completed through conversation; a Flask web application may serve as the testing prototype. | A separate participant web form is not mandatory in the final workflow. A Flask chat prototype, if used, exercises the same agents and database-backed state without substituting for later WhatsApp integration acceptance. |

Version 1.1 preserves FR-01–FR-26 and their detailed acceptance structure while updating course scope, conversational behavior, agent coordination, memory, pending materials and policy dependencies. Supervisor clarification establishes the working direction; approval of the complete requirements baseline remains pending.

## Introduction

Q&M currently handles training enquiries and enrollment administration manually through WhatsApp. Staff repeatedly explain funding eligibility, course benefits, entry requirements and possible job pathways, and follow up with people who stop responding. This consumes operations time and delays answers as enquiry volume grows.

Enrollment adds repeated collection of participant information, Excel-based invoice preparation, signing and emailing documents, payment instructions, screenshot checking and accounting coordination. The proposed system will connect these activities through a shared WhatsApp entry point and Modules A, B and C, retaining staff responsibility for uncertain payments and policy decisions. This Week 1 document defines the expected behavior and future acceptance evidence; it does not certify that the system exists or complies with every obligation.

### Feature Summary

A WhatsApp chatbot coordinated by CrewAI uses natural-language conversation and database-backed memory for Modules A and B to support enquiries and guided enrollment for the 2-Day Basic Certificate in Dental Assisting, with invoicing, payment screenshot processing, email delivery and staff accounting portals.

### Business Value

| Objective | Expected value | Evidence to collect later |
|---|---|---|
| BO1 | Reduce repetitive enquiry handling while keeping answers grounded in approved information. | FAQ and routing accuracy; manual enquiry workload baseline and comparison. |
| BO2 | Reduce repeated data entry and invoice errors for the initial certificate course while preparing the system for later course expansion. | Mandatory-field checks, document accuracy, enrollment processing measurements and extensibility design evidence. |
| BO3 | Reduce routine payment administration while keeping exceptions accountable. | False-match rate, review outcomes, payment-to-receipt records and accounting reports. |
| BO4 | Protect participant data and enable Q&M to operate the service after handover. | Access-control and privacy validation, recovery demonstrations, documentation and training evidence. |

Workload reduction, conversion improvement and processing-time improvements are expected benefits, not approved numerical commitments. Their baselines and targets are Q14.

### Scope

| Area | Included in the initial MVP scope |
|---|---|
| Shared service | One WhatsApp entry point; CrewAI coordination through the Intent Classification Agent; natural-language conversation; database-backed memory for Modules A and B across messages and previous days; participant record lookup. |
| Module A — AI Chatbot & Lead Nurturing | FAQ/Enquiry Agent for the 2-Day Basic Certificate in Dental Assisting: approved course details and FAQs, quick replies alongside free text, general funding guidance, non-sensitive enquiry context, follow-ups and human escalation. |
| Module B — Enrollment, Invoice & Payment Pipeline | Enrollment Agent continuously guides collection and validation of all six fields through conversation, presents a confirmation summary, stores confirmed enrollment in the database, and supports signed PDF invoices, email delivery, payment instructions and status tracking. |
| Module C — Payment Verification & Accounts | Payment Verification Agent handles WhatsApp and email screenshot intake, AI-assisted comparison, auto-confirmation under approved matching rules, mandatory staff exception review, payment records, receipts and accountant-approved credit notes. |
| Course extensibility | Database entities and course-related behavior support adding more courses later. Only the 2-Day Basic Certificate in Dental Assisting must be available in the initial release. |
| Staff tools | Operations dashboard, escalation inbox, content maintenance, password-protected accountant portal, payment filters and scheduled accounting reports. |
| Delivery and operation | Security and PDPA controls, staging and production deployment, backup/restore, monitoring, documentation, two staff training sessions, handover and 30-day support. These are future deliverables. |

The initial participant-facing offering is the 2-Day Basic Certificate in Dental Assisting. Additional live courses are a later expansion; the initial database and system must accommodate them. Unsupported or unavailable courses/intakes must not be presented as enrollable. Enrollment is completed through the conversational interface, with no mandatory participant web form. A Flask web application may be used as a chat-based testing prototype. Slash commands are optional testing/development shortcuts only. Email remains an approved screenshot submission and document delivery channel, not a separately specified general-purpose chatbot.

### Confirmed Agent Coordination

| Component | Required responsibility | Related requirements |
|---|---|---|
| CrewAI | Coordinate classification, specialist-agent routing and workflow execution using the participant's current context. | FR-01–FR-03, FR-24 |
| Intent Classification Agent | Determine whether the inbound message concerns an enquiry/FAQ, enrollment or payment; request clarification where intent is ambiguous. | FR-01 |
| FAQ/Enquiry Agent — Module A | Answer from approved course/FAQ content and use database-backed history to continue enquiries across messages and previous days. | FR-02, FR-04–FR-06, FR-13 |
| Enrollment Agent — Module B | Retrieve current enrollment context, ask follow-up questions, validate six required fields, obtain confirmation and store the confirmed enrollment. | FR-02, FR-07–FR-11 |
| Payment Verification Agent — Module C | Extract and compare payment evidence, apply approved matching rules and route mismatched/unreadable evidence to staff. | FR-14–FR-20 |

The exact LLM may be configured by role. Model selection must preserve these responsibilities and the specified privacy/authorization boundaries. The database stores conversation history for Modules A and B and structured enrollment/payment state used by the workflow; conversation memory does not itself authorize a financial action.

### Pending Q&M Materials

| Required official input | Intended use | Status / question |
|---|---|---|
| Initial certificate course information, entry requirements, learning outcomes and FAQs | Module A answers and Module B enrollment guidance. | Pending confirmation from Mr. Wee/Q&M — Q01, Q03 |
| Fees, funding/subsidy rules and intake schedules | Availability checks, funding guidance and invoice calculations. | Pending confirmation from Mr. Wee/Q&M — Q01, Q03 |
| PayNow recipient details, company UEN and QR code | Payment instructions and screenshot comparison. | Pending confirmation from Mr. Wee/Q&M — Q05 |
| Official invoices and approved invoice, receipt and credit-note templates | Document generation, branding, signing and financial-document validation. | Pending confirmation from Mr. Wee/Q&M — Q05 |
| WhatsApp and email messaging templates, including follow-ups and payment/claim instructions | Participant communications and document delivery. | Pending confirmation from Mr. Wee/Q&M — Q04, Q06, Q12 |

Q&M will provide these materials later. Their delivery is a confirmed dependency; their contents and approval are outstanding. Draft layouts or test fixtures must be identified as non-production material and cannot establish prices, funding, payment details or business policy.

### Users and Responsibilities

| User or stakeholder | Needs and responsibility |
|---|---|
| Prospective participant / lead | Ask naturally about the initial certificate course and its intakes, receive permitted follow-ups and reach staff without giving NRIC or DOB. |
| Enrolling participant | Supply six mandatory fields after enrollment starts, correct errors, receive invoices, submit payment evidence and request their own status/documents. |
| Q&M operations staff | Maintain approved course/FAQ content, monitor enrollment and delivery status, respond to escalations and resolve assigned issues. |
| Q&M accounting staff | Review payment evidence, confirm or reject exceptions, review balances and overdue records, issue/resend receipts and approve credit notes. |
| Q&M system administrator | Manage staff access, configuration, monitoring, backup and recovery within assigned permissions. |
| Q&M privacy/business owner | Confirm data purposes, privacy notices, retention, permitted processing and business rules; exact named owners are Q10 and Q16. |
| NYP project team / Mr. Wee | Review scope and specifications, implement and validate later phases, prepare documentation, training and handover. |

## Requirements

Each numbered requirement has a stable identifier `FR-01` through `FR-26`. A criterion is referenced as, for example, `FR-08.AC3`. Priority expresses importance within the stated scope; complexity is a preliminary planning estimate, not completed design. Additional Details identify dependencies, assumptions and provenance. Open-question IDs refer to the unresolved questions register.

### Requirement 1: CrewAI Coordination and Intent Classification (FR-01)

**User Story:** As a participant, I want one WhatsApp conversation to handle enquiries, enrollment and payment, so that I can complete the journey without finding separate chatbot numbers.

#### Acceptance Criteria

1. WHEN a valid inbound WhatsApp message arrives, the system SHALL use CrewAI to invoke the Intent Classification Agent with the message text or attachment and permitted current context to determine enquiry/FAQ, enrollment or payment intent.
2. IF a message has ambiguous or conflicting intents, the Intent Classification Agent SHALL request clarification before creating an enrollment or changing financial state.
3. WHEN a participant asks an FAQ during enrollment, the system SHALL route it through CrewAI to the FAQ/Enquiry Agent while preserving the Enrollment Agent's draft and context for continuation.
4. IF an intent cannot be resolved through clarification, the system SHALL create a staff escalation with the unresolved request and permitted context.
5. WHEN an intent is determined, the system SHALL use CrewAI to route enquiry/FAQ messages to the FAQ/Enquiry Agent for Module A, enrollment messages to the Enrollment Agent for Module B and payment messages to the Payment Verification Agent for Module C.
6. WHEN an approved LLM configuration changes, the system SHALL retain the same CrewAI agent responsibilities, routing contract and authorization/validation requirements.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-02, FR-03, FR-06 and FR-23.
- **Assumptions**: AS1; ambiguity and escalation rules require Q04.
- **Source / Objectives**: S1 pp. 2–8 for module responsibilities; D1–D2 and D9 supersede the original coordination choice; DR for safe ambiguity handling; BO1–BO3.

### Requirement 2: Conversation Memory and Continuity (FR-02)

**User Story:** As a returning participant, I want the chatbot to remember relevant context, so that I can continue without repeating valid information.

#### Acceptance Criteria

1. WHEN a participant sends a message to Module A or B, including on a later day within the retention period once approved, the system SHALL retrieve the participant's permitted conversation history and current workflow context from the database before the relevant agent responds.
2. WHEN a participant corrects a draft field, the system SHALL use the corrected value for subsequent validation and present the updated enrollment summary before submission.
3. WHILE a participant continues a natural-language conversation or moves between Modules A and B, the system SHALL preserve the authorized course selection, collected draft fields and current workflow context unless the participant changes them.
4. IF memory has expired or is unavailable, the system SHALL explain that conversational context must be re-established and retrieve separately retained enrollment records only under their applicable access and retention rules.
5. WHILE processing a participant's conversation, the system SHALL isolate its memory from other participants and apply FR-23 to NRIC, DOB and retained history.
6. WHEN a Module A or B turn changes permitted conversation context or enrollment draft information, the system SHALL persist that history and context in the database so the participant can resume across messages and previous days without depending on an open browser session or a running process's temporary memory.
7. IF an agent resumes from history that conflicts with a newer confirmed database record, the system SHALL use the current record for enrollment and financial facts and clarify any unresolved discrepancy with the participant.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-12, FR-23; NFR-SEC1–NFR-SEC5 and NFR-PRI1.
- **Assumptions**: AS4; memory for Modules A and B across previous days is confirmed by D1. Exact duration, permitted history content and deletion rules are Pending confirmation from Mr. Wee/Q&M (Q10); no numerical period is assumed.
- **Source / Objectives**: S1 pp. 5–7, 10–11; D1, D5, D8–D9 and D11; DR for correction, expiry and stale-context behavior; BO1, BO2, BO4.

### Requirement 3: Natural-Language Conversation and Help (FR-03)

**User Story:** As a participant, I want to use ordinary messages and receive guided help, so that I can complete the journey without learning commands or strict input formats.

#### Acceptance Criteria

1. WHEN a participant sends a supported natural-language request, the system SHALL use the CrewAI-coordinated agents to carry out the authorized enquiry, enrollment, payment, status or document-request workflow without requiring a slash command.
2. WHEN a participant requests help, the system SHALL explain the available conversational actions and the next step in their current context using ordinary language.
3. IF a participant's request or enrollment response lacks information, the system SHALL collect it through follow-up questions while retaining valid draft fields instead of demanding all information in one formatted message.
4. IF input is unrecognized or ambiguous, the system SHALL explain what needs clarification and offer conversational help without executing an unintended operation.
5. WHEN natural-language enrollment intent is detected, the system SHALL invoke the Enrollment Agent and begin guided enrollment before accepting NRIC or DOB into enrollment storage, subject to FR-23.
6. WHERE optional testing/development slash shortcuts are enabled, the system SHALL apply the same workflow validation, access controls and privacy boundaries as the conversational path without making those shortcuts a participant prerequisite.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-01, FR-02, FR-07–FR-09, FR-12, FR-14 and FR-18.
- **Assumptions**: AS2; natural-language completion is mandatory, while retaining development shortcuts is optional and does not require participant command support.
- **Source / Objectives**: S1 pp. 2–3 and 13–17 for workflow topics; D1–D5, D8–D9 and D12 supersede mandatory command formats; BO1–BO3.

The following names may be retained as optional testing/development shortcuts. This is not a participant command contract or a mandatory implementation list. Each enabled shortcut enters the corresponding conversational workflow; no pipe-separated enrollment payload is required. Participant instructions and acceptance scenarios use natural language.

| Optional testing/development shortcut | Behavior if retained |
|---|---|
| `/help` | Show conversational help in the testing/development interface. |
| `/courses` | Show the initial certificate course; later approved courses can use the same course-data structure. |
| `/fees` | Request approved fees and funding information in the current course context. |
| `/schedule` | Request approved upcoming intakes in the current course context. |
| `/sfc` | Provide general SkillsFuture information and approved official self-service guidance. |
| `/enroll` | Start guided enrollment and collect all six required fields. |
| `/mystatus` | Retrieve the verified sender's enrollment status; ask which of their records if ambiguous. |
| `/invoice` | Resend the selected existing invoice to the email on record. |
| `/pay` with an image, or `/pay` followed by an image | Submit payment evidence; a missing image triggers attachment guidance, not payment confirmation. |
| `/receipt` | Resend the selected existing receipt to the email on record. |

### Requirement 4: Initial Certificate Course, Extensibility and Approved FAQ Answers (FR-04)

**User Story:** As a prospective participant, I want accurate information about the 2-Day Basic Certificate in Dental Assisting, so that I can assess the course and choose a suitable intake.

#### Acceptance Criteria

1. WHEN a participant first contacts the chatbot, the system SHALL introduce natural-language assistance for the certificate course, fees/funding, schedules, enrollment and staff help, with quick replies available alongside free-text conversation.
2. WHEN a participant asks which course is offered in the initial MVP, the FAQ/Enquiry Agent SHALL identify the 2-Day Basic Certificate in Dental Assisting and distinguish its confirmed course scope from any official details still awaiting Q&M input.
3. WHEN a participant asks about the supported course, the FAQ/Enquiry Agent SHALL answer from approved content covering fees, upcoming intakes, learning outcomes, entry requirements, funding and job pathways where that content exists.
4. IF an answer or current offering is absent from approved content, the system SHALL state that confirmation is needed and offer staff escalation without inventing prices, eligibility, availability or employment guarantees.
5. IF a requested course is outside the initial scope or a requested intake is unavailable, the system SHALL explain that limitation and offer approved intakes of the supported course or staff assistance without confirming an unsupported enrollment.
6. WHEN the initial system and database are designed, the project team SHALL represent courses and their related intakes, fees, content and enrollments using distinct course identities so additional courses can be added later without redesigning the core schema or enrollment workflow.
7. WHEN later course expansion is evaluated in a non-production extensibility check, the system SHALL associate the additional course's content, intake, enrollment and financial records with its own course identity without changing existing certificate-course records.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-06 and FR-22.
- **Assumptions**: AS2; the initial course is confirmed by D3. Its official information, schedules, capacity rules and approved content require Q01 and Q03. Extensibility validation does not require launching another live course in the MVP.
- **Source / Objectives**: S1 pp. 1–4, 12–14; D3 and D10; DR for missing content; BO1, BO2.

### Requirement 5: Funding and Payment Guidance (FR-05)

**User Story:** As a prospective participant, I want clear funding and payment instructions, so that I can check my options independently.

#### Acceptance Criteria

1. WHEN a participant asks about SkillsFuture, Mid-Career SkillsFuture Credits or subsidies, the system SHALL provide only Q&M-approved current guidance and distinguish general information from confirmed individual entitlement.
2. WHEN a participant wants to check their SkillsFuture balance, the system SHALL provide the approved official MySkillsFuture portal link and self-service steps.
3. IF a participant requests an automated Singpass login, balance lookup or claim submission, the system SHALL explain the supported self-service route without requesting government credentials or performing the excluded integration.
4. WHEN an enrolling participant requests payment instructions, the system SHALL provide the approved PayNow and SkillsFuture instructions applicable to their enrollment without inferring a subsidy from age alone.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-04, FR-10 and FR-22.
- **Assumptions**: AS2; approved funding rules, links and claim handling require Q03 and Q06.
- **Source / Objectives**: S1 pp. 2–4, 8, 13–14; D3, D5 and D10; DR for unconfirmed entitlement; BO1, BO2.

### Requirement 6: Human Escalation (FR-06)

**User Story:** As an operations staff member, I want uncertain or sensitive requests in a review queue, so that I can give participants an accountable response.

#### Acceptance Criteria

1. WHEN a participant asks for staff or a query is complex, sensitive or unresolved, the system SHALL create an escalation with a reason, participant reference and permitted conversation context.
2. WHEN an escalation is created, the system SHALL acknowledge the handoff to the participant without promising an unapproved response time.
3. WHILE staff handling is active, the system SHALL preserve the handoff status and suppress automated nurture messages for that lead.
4. WHEN authorized staff record a resolution and return the conversation to automation, the system SHALL record the actor and outcome and resume from the resolved context.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-13, FR-21 and FR-23.
- **Assumptions**: AS3; staff ownership, notification channel, hours and response commitments require Q04.
- **Source / Objectives**: S1 pp. 3, 7–10, 12; DR for handoff state; BO1, BO4.

### Requirement 7: Enrollment Start and Data Collection Boundary (FR-07)

**User Story:** As a prospective participant, I want to ask questions before providing sensitive details, so that identity data is requested only when I choose to enroll.

#### Acceptance Criteria

1. WHEN the Intent Classification Agent detects natural-language enrollment intent, the Enrollment Agent SHALL begin or resume guided enrollment using the participant's database-backed context and explain the six required fields and the privacy notice once its wording is approved.
2. WHILE a participant is making general enquiries or receiving lead follow-ups without starting enrollment, the system SHALL refrain from requesting or intentionally persisting NRIC or DOB as lead data.
3. IF a participant sends NRIC or DOB before enrollment starts, the system SHALL exclude those values from persisted application conversation memory, lead records and routine logs, and explain that sensitive details are collected during enrollment.
4. WHEN enrollment has started and the approved privacy prerequisites are satisfied, the Enrollment Agent SHALL collect course, full name, NRIC, date of birth, email and preferred intake date through guided natural-language messages.
5. IF a participant abandons enrollment, the system SHALL stop prompting for sensitive fields and handle the draft under the approved retention rules without marking it Enrolled.
6. WHILE an enrollment conversation is active and any required field is missing or needs correction, the Enrollment Agent SHALL continue asking relevant follow-up questions on subsequent participant turns until all six fields are available and valid, or the participant pauses, abandons or requests staff assistance.
7. WHEN an enrolling participant pauses and returns on a later day within the retention period once approved, the Enrollment Agent SHALL retrieve the draft and permitted history from the database and resume from the outstanding question without demanding that valid fields be repeated.
8. WHEN the course field is collected during the initial MVP enrollment, the Enrollment Agent SHALL explicitly identify the 2-Day Basic Certificate in Dental Assisting and obtain the participant's confirmation of that course rather than omit the required course field because only one course is offered.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-02, FR-08 and FR-23.
- **Assumptions**: AS4; Q10 governs notice, consent and deletion. Provider-held message retention is a separate unresolved processing issue and is not claimed to be under application control.
- **Source / Objectives**: S1 pp. 2–3, 7–8, 10–11; D1–D5, D9 and D11–D12; DR for unsolicited sensitive data and pause handling; BO2, BO4.

### Requirement 8: Mandatory Enrollment Validation (FR-08)

**User Story:** As an enrolling participant, I want specific correction guidance, so that my enrollment is accurate before an invoice is created.

#### Acceptance Criteria

1. IF any of course, full name, NRIC, date of birth, email or preferred intake date is missing or invalid, the system SHALL keep the enrollment incomplete and prevent enrollment completion and invoice generation.
2. WHEN a field fails validation, the system SHALL identify the field and correction needed while retaining other valid draft fields under the applicable privacy rules.
3. WHEN validating enrollment data, the Enrollment Agent SHALL check the selected course against the initial certificate scope and the intake against its approved schedule, require a non-empty full name, apply the approved NRIC validation rule, require a valid calendar DOB that is not in the future, and validate email syntax.
4. IF a date is ambiguous, the system SHALL ask the participant to clarify rather than silently choosing a date interpretation.
5. WHEN all six fields pass validation, the Enrollment Agent SHALL show the participant a confirmation summary, apply the NRIC/DOB display and masking policy once approved under Q10, and request confirmation before committing the enrollment.
6. IF an eligibility decision depends on unavailable funding or admission rules, the system SHALL refer the decision to staff rather than invent an age cutoff, subsidy or admission rule.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-04, FR-07, FR-09 and FR-23.
- **Assumptions**: AS2; Q01–Q03 cover field formats, allowed identifiers, intake rules and eligibility. No FIN substitution or alternative to required NRIC is authorized in this draft. Summary masking/display rules are Pending confirmation from Mr. Wee/Q&M (Q10); this draft does not choose a masking pattern.
- **Source / Objectives**: S1 pp. 2–3, 7–8, 14; D1–D5, D9 and D11; DR for summary and ambiguity; BO2, BO4.

### Requirement 9: Enrollment Records and Lifecycle (FR-09)

**User Story:** As an operations staff member, I want one consistent enrollment record, so that each participant's progress can be tracked reliably.

#### Acceptance Criteria

1. WHEN a participant confirms a validated six-field draft through conversation, the Enrollment Agent SHALL store the confirmed enrollment in the database and create an enrollment reference linked to the verified WhatsApp number, course identity and preferred intake date.
2. WHEN an enrollment milestone succeeds, the system SHALL record its status, timestamp and source event in the central record.
3. IF invoice generation, payment review or document delivery fails, the system SHALL retain the last justified lifecycle status and record the failure separately.
4. IF the same message or operation is retried, the system SHALL avoid creating a duplicate enrollment, invoice, payment confirmation, receipt or credit note for that same operation.
5. IF a participant has multiple enrollments, the system SHALL keep their course, intake, invoice and payment associations separate.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-08, FR-10–FR-12 and FR-15–FR-19.
- **Assumptions**: AS4; duplicate business enrollments, capacity and intake allocation require Q01 and Q02. A preferred intake is not an invented seat-reservation guarantee.
- **Source / Objectives**: S1 pp. 3, 6–9, 11; D3–D4 and D9; DR for retry safety and state distinctions; BO2, BO3.

Lifecycle terms derive from S1. Operational flags below refine visibility without claiming new Q&M financial policies.

| Lifecycle status / operational flag | Entry condition |
|---|---|
| Enquiry | A lead exists without a completed enrollment; any enrollment draft remains incomplete. |
| Enrolled | All six fields are validated and the participant confirms submission under the approved admission/intake rules. |
| Invoice Sent | The existing invoice has reached the approved email-delivery confirmation milestone; Q06 defines whether provider acceptance or delivered notification is required. |
| Awaiting Payment | Invoice Sent is recorded and confirmed payment remains outstanding. Preserve the Invoice Sent timestamp even if the next state follows immediately. |
| Paid | A payment is auto-confirmed under approved rules or explicitly confirmed by authorized staff. |
| Receipt Issued | A receipt has been generated for confirmed payment; its email delivery status is tracked separately. |
| Review Required | Payment evidence needs staff action; this flag does not by itself advance or reverse the financial lifecycle. |
| Delivery Failed | A document delivery failed; retain the document and permit an authorized retry. |
| Overdue | An unpaid invoice meets an approved due-date rule; do not calculate this from an invented deadline. |
| Credit Note Required / Approved / Issued | Separate accounting workflow flags, applied under approved policy; a request alone does not cancel a balance. |

### Requirement 10: Accurate Signed PDF Invoices (FR-10)

**User Story:** As an enrolled participant, I want an accurate invoice, so that I know the course charges and how much is payable.

#### Acceptance Criteria

1. WHEN enrollment is complete and approved pricing is available, the system SHALL generate a uniquely identified PDF invoice using the approved Q&M branding and signing arrangement.
2. WHEN generating the invoice, the system SHALL use the validated participant details, selected course and intake, fee breakdown, approved subsidy amount and net payable, together with the approved company UEN and PayNow details.
3. IF a required price, subsidy decision, invoice template or signing asset is unavailable, the system SHALL hold invoice generation for staff resolution without inventing financial content.
4. WHEN an invoice is regenerated or corrected by an authorized workflow, the system SHALL preserve its relationship to the enrollment and maintain a record of the correction under the approved numbering and correction rules.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-08–FR-09, FR-22 and FR-23.
- **Assumptions**: AS2; Q03 and Q05 determine pricing, tax, subsidy evidence, numbering, signature and official document templates. NRIC/DOB display and masking are Pending confirmation from Mr. Wee/Q&M (Q10); document field requirements do not establish a masking policy.
- **Source / Objectives**: S1 pp. 3, 8, 10–12; D4, D10 and D11; BO2, BO4.

### Requirement 11: Invoice and Instructions Delivery (FR-11)

**User Story:** As an enrolled participant, I want my invoice and payment instructions emailed to me, so that I can pay using the supported methods.

#### Acceptance Criteria

1. WHEN an invoice is ready, the system SHALL email the signed PDF invoice, approved SkillsFuture claim instructions and PayNow QR code/company UEN to the validated email on record.
2. WHEN the configured delivery confirmation is received, the system SHALL record the delivery milestone and send a WhatsApp enrollment/invoice notification using the approved message template and identity-data display policy.
3. IF invoice email delivery fails, the system SHALL record the failure, notify the staff queue and allow retry of the existing document without representing it as successfully delivered.
4. WHEN an authorized invoice resend is requested, the system SHALL resend the existing applicable invoice rather than create a second charge.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-09–FR-10, FR-12 and FR-21.
- **Assumptions**: AS1–AS2; sending identity, delivery milestone, retry timing and instructions require Q06. Notification masking/display policy is Pending confirmation from Mr. Wee/Q&M (Q10).
- **Source / Objectives**: S1 pp. 3, 8, 12, 14; D8, D10 and D11; DR for delivery failure; BO2.

### Requirement 12: Participant Status and Document Requests (FR-12)

**User Story:** As a participant, I want to retrieve my status, invoice or receipt through my WhatsApp number, so that I can get routine information without repeating sensitive identity details.

#### Acceptance Criteria

1. WHEN a normal status, invoice or receipt request arrives from a verified WhatsApp sender, the system SHALL authorize lookup using that sender's association with the enrollment records without requiring NRIC, DOB, an additional OTP or a separate login.
2. WHEN the sender requests status, the system SHALL show their selected enrollment's course, intake, lifecycle status, applicable invoice reference and next action without revealing another participant's data.
3. IF more than one enrollment belongs to the sender and the intended record is unclear, the system SHALL ask the sender to select among their own records before disclosing details or resending documents.
4. WHEN the sender requests an existing invoice or receipt, the system SHALL resend it to the email address already recorded for that enrollment.
5. IF no matching enrollment or requested document exists, the system SHALL explain that outcome and offer the relevant enrollment or staff-help path without fabricating a document.
6. IF a request changes a phone number, email address or ownership association, the system SHALL refer it to the separately approved account-change process instead of treating it as a normal lookup or resend.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-09, FR-11, FR-18 and FR-21.
- **Assumptions**: AS1 and AS4; Q11 covers exceptional record changes. D8 is sufficient for normal requests and is not reopened by Q11.
- **Source / Objectives**: S1 pp. 14, 17; D8; DR for multiple records and exceptional changes; BO2–BO4.

### Requirement 13: Lead Follow-Up Scheduling (FR-13)

**User Story:** As an operations staff member, I want permitted reminders for unresponsive leads, so that interested participants can continue without individual manual prompting.

#### Acceptance Criteria

1. WHEN an eligible unresponsive lead reaches a configured 24-hour, 72-hour or 7-day reminder milestone, the system SHALL send the approved contextual WhatsApp follow-up subject to consent and platform requirements.
2. IF a lead responds, enrolls, opts out or enters staff handling, the system SHALL suppress pending nurture reminders that no longer apply.
3. WHEN a reminder is sent or fails, the system SHALL record its milestone, timestamp and delivery outcome without duplicating the same milestone on scheduler retries.
4. IF an approved template, consent prerequisite or platform permission is missing, the system SHALL hold the reminder and expose the reason to operations staff.

#### Additional Details

- **Priority**: Medium
- **Complexity**: Medium
- **Dependencies**: FR-02, FR-06, FR-22 and FR-23.
- **Assumptions**: AS1–AS3; S1 alternates between initial-contact and last-contact timing, so Q04 must settle the clock origin, reset rules and allowed scheduler delay. The three stated milestones remain in scope.
- **Source / Objectives**: S1 pp. 2, 7, 10, 12; D5 and D10; DR for suppression and deduplication; BO1, BO4.

### Requirement 14: WhatsApp and Email Payment Screenshot Intake (FR-14)

**User Story:** As a participant, I want to send payment screenshots by WhatsApp or email, so that I can submit evidence through either supported channel.

#### Acceptance Criteria

1. WHEN a payment screenshot arrives through WhatsApp, the system SHALL route it through CrewAI to the Payment Verification Agent in Module C and associate it with an authorized enrollment or request clarification, without requiring a command caption.
2. WHEN a payment screenshot arrives at the designated email intake address, the system SHALL accept it into the same Module C review/verification workflow and resolve its enrollment association using the approved email-matching procedure.
3. WHERE WhatsApp or email permits a screenshot submission, the system SHALL accept it without adding business limits on file size, image count, submission frequency or resubmission count beyond the platform limits.
4. IF a participant indicates payment submission without providing an image, the system SHALL explain how to attach or subsequently send the screenshot and preserve the payment-submission context without confirming payment.
5. IF an image cannot be associated unambiguously with an enrollment, the system SHALL retain it for staff review without changing payment status or disclosing a participant record to an unverified email sender.
6. IF platform delivery or media retrieval fails, the system SHALL record the failure and provide available retry guidance without treating the payment as confirmed.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-01–FR-02, FR-09, FR-15–FR-16 and FR-23.
- **Assumptions**: AS1; Q07 covers the mailbox, association procedure and provider capabilities. Channel limits do not remove mandatory review of unreadable or mismatched evidence. Abuse controls must not become additional business screenshot quotas.
- **Source / Objectives**: S1 pp. 3, 8, 13–15; D2, D6–D7 and D9; DR for email association and retrieval failure; BO3, BO4.

### Requirement 15: AI-Assisted Payment Comparison (FR-15)

**User Story:** As an accountant, I want payment evidence compared with invoice data, so that straightforward matches can be processed and uncertain cases identified.

#### Acceptance Criteria

1. WHEN usable payment evidence is associated with an invoice, the Payment Verification Agent SHALL extract the visible amount, recipient details, transaction reference and transaction date where present, preserving uncertainty for missing or unclear values.
2. WHEN evaluating evidence, the Payment Verification Agent SHALL compare the extracted amount with the invoice amount due and check the recipient and reference under approved verification rules.
3. IF all approved automatic-match conditions are satisfied and no exception is detected, the system SHALL record an automatic confirmation and trigger FR-17.
4. IF the screenshot is mismatched, unreadable, ambiguous, potentially duplicated or below the approved confidence threshold, the system SHALL record Review Required and route it to staff without automatically marking the enrollment Paid.
5. IF automatic-match thresholds or required verification rules are not approved, the system SHALL route submissions to staff review until those rules are configured.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-10, FR-14, FR-16 and FR-17.
- **Assumptions**: AS3; Q08 covers thresholds, matching tolerances, expected recipient data, duplicate evidence and partial/multiple payments. A screenshot match is an evidence decision, not a bank API confirmation.
- **Source / Objectives**: S1 pp. 4, 8, 10–11, 13; D7, D9 and D10; DR for unapproved rules; BO3, BO4.

### Requirement 16: Mandatory Staff Review of Payment Exceptions (FR-16)

**User Story:** As an authorized payment reviewer, I want mismatched and unreadable screenshots with their discrepancies, so that I can resolve them before a payment is accepted.

#### Acceptance Criteria

1. WHEN any screenshot is classified as mismatched or unreadable, the system SHALL create a staff review item containing the evidence, invoice association where known, extracted values and reason for review.
2. WHILE review is unresolved, the system SHALL leave the affected unconfirmed payment unconfirmed and withhold any new receipt dependent on that payment.
3. WHEN authorized staff confirm or reject a submission, the system SHALL record their identity, decision, reason and timestamp before applying the corresponding payment action.
4. IF the system asks for a replacement screenshot or a participant submits one, the system SHALL retain the original review history and link the new evidence without silently dismissing the staff-review obligation.
5. WHEN an exception is referred to staff, the system SHALL tell the participant that review is pending and provide any appropriate correction guidance without claiming payment success.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-14–FR-15, FR-17 and FR-21.
- **Assumptions**: AS3; Q04 and Q08 define authorized reviewers and resolution policies. A later problematic upload must not automatically reverse a previously confirmed payment.
- **Source / Objectives**: S1 pp. 4, 8, 11; D7 overrides resend-only implications on p. 15; BO3, BO4.

### Requirement 17: Payment Records and Reconciliation (FR-17)

**User Story:** As an accountant, I want confirmed payments reflected consistently, so that balances and receipts are based on an auditable record.

#### Acceptance Criteria

1. WHEN an automatic or staff payment confirmation is committed, the system SHALL store the invoice/enrollment association, confirmed amount, available transaction details, evidence reference and decision source.
2. WHEN the confirmation establishes that the approved amount due is satisfied, the system SHALL advance the enrollment to Paid and trigger receipt generation.
3. IF payment evidence is received again through either channel, the system SHALL detect repeated evidence where identifiable and prevent counting the same confirmed transaction twice.
4. IF a partial payment, overpayment, combined payment or unexplained reference prevents an approved decision, the system SHALL send it to staff review without inventing installment, tolerance or refund rules.
5. WHEN an authorized payment correction occurs, the system SHALL preserve the previous decision and the corrective action in the audit trail rather than silently overwrite financial history.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-09, FR-15–FR-16, FR-18 and FR-20.
- **Assumptions**: AS3; Q08 governs balance and reconciliation rules, including SkillsFuture settlement evidence.
- **Source / Objectives**: S1 pp. 2, 4–5, 8–9; DR for financial consistency; BO3.

### Requirement 18: Receipt Generation and Resend (FR-18)

**User Story:** As a paid participant, I want a receipt and an easy way to request it again, so that I have a record of my confirmed payment.

#### Acceptance Criteria

1. WHEN FR-17 confirms payment and receipt prerequisites are available, the system SHALL generate a uniquely identified PDF receipt from the approved template and link it to the payment and invoice.
2. WHEN the receipt is generated, the system SHALL email it to the participant's recorded address and send a WhatsApp notification with an accurate delivery outcome.
3. IF receipt generation or delivery fails, the system SHALL preserve Paid status, record the specific pending or failed step and allow retry without generating a duplicate receipt for the same operation.
4. WHEN an authorized normal receipt request is received, the system SHALL resend the existing receipt under FR-12 without requiring additional participant identity fields.
5. IF payment remains unconfirmed, the system SHALL explain that a receipt is unavailable and show the applicable review or payment next step instead of generating one.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-12, FR-17 and FR-22.
- **Assumptions**: AS2–AS3; Q05 and Q06 determine document rules and delivery behavior.
- **Source / Objectives**: S1 pp. 4, 8–9, 12–14; D8 and D10; BO2, BO3.

### Requirement 19: Credit Notes and Cancellation Review (FR-19)

**User Story:** As an accountant, I want to review credit-note requests before issuance, so that cancellation and unpaid-account adjustments follow approved policy.

#### Acceptance Criteria

1. WHEN an unpaid or cancelled enrollment meets an approved credit-note trigger or authorized staff raise a request, the system SHALL create a Credit Note Required item linked to the enrollment and invoice.
2. WHILE a credit-note request awaits approval, the system SHALL preserve the existing accounting balance without issuing an approved credit note automatically.
3. WHEN an authorized accountant approves the request, the system SHALL record the decision and generate and email the approved credit-note PDF under the applicable document rules.
4. IF the request is rejected or policy is unresolved, the system SHALL retain the decision or pending reason without applying an unsupported cancellation, refund or write-off.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-09, FR-17, FR-20–FR-22.
- **Assumptions**: AS3; all eligibility, cancellation, refund and approval limits require Q09. No refund execution capability is inferred from credit-note generation.
- **Source / Objectives**: S1 pp. 2, 4, 8–9, 12; D10; DR for unresolved policy handling; BO3.

### Requirement 20: Accountant Portal and Reports (FR-20)

**User Story:** As an accountant, I want a protected view of payment work and scheduled reports, so that I can reconcile accounts and resolve outstanding items.

#### Acceptance Criteria

1. WHEN authenticated accounting staff open the portal, the system SHALL display permitted enrollments with filters for payment status, pending receipts, review items, overdue accounts and credit-note requests.
2. WHEN a reviewer opens an authorized payment item, the system SHALL show its invoice, associated evidence and decision history and expose only actions permitted to that role.
3. WHEN the configured nightly accounting-report schedule runs, the system SHALL generate a CSV summary by payment status and email it to approved accounting recipients.
4. IF no approved due-date rule exists, the system SHALL identify overdue classification as unconfigured rather than assign an invented overdue date.
5. IF report generation or delivery fails, the system SHALL record the failure and notify the responsible staff without reporting successful delivery.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-09, FR-16–FR-19, FR-21 and FR-23.
- **Assumptions**: AS3; Q08–Q09 and Q12 cover due dates, report fields, recipients and nightly run time. Reports complement the portal; they do not replace the requested portal.
- **Source / Objectives**: S1 pp. 4–5, 8–9, 12; DR for failure visibility; BO3, BO4.

### Requirement 21: Operations Dashboard and Staff Access (FR-21)

**User Story:** As an operations staff member, I want a secure dashboard of enrollments and exceptions, so that I can act on current information within my responsibilities.

#### Acceptance Criteria

1. WHEN authenticated operations staff open the dashboard, the system SHALL show permitted enrollment statuses, participant/course references, escalations and delivery failures from the central records.
2. WHEN a workflow changes a record, the system SHALL reflect the committed state in the dashboard within the approved freshness target and show the latest update time.
3. IF a staff user is unauthenticated or lacks permission, the system SHALL deny access to the protected record or operation, including direct URL and API access.
4. WHEN an authorized administrator grants, changes or revokes staff access, the system SHALL record the actor, affected account, changed permissions and time.
5. WHEN staff access sensitive evidence or change enrollment/financial data, the system SHALL apply role permissions and record the action for audit review.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-06, FR-09, FR-16, FR-20 and FR-23; NFR-SEC1–NFR-SEC5.
- **Assumptions**: AS3; Q11 defines the role matrix and staff authentication/session settings; Q13 defines freshness. Staff login requirements do not impose a participant login on D8 requests.
- **Source / Objectives**: S1 pp. 3–4, 8, 10–12; DR for permission lifecycle; BO2–BO4.

### Requirement 22: Approved Content and Template Maintenance (FR-22)

**User Story:** As an authorized Q&M content maintainer, I want to update courses, FAQs and templates, so that the system remains accurate after handover.

#### Acceptance Criteria

1. WHEN an authorized maintainer updates course offerings, FAQ content or message/document templates, the system SHALL record the version, editor and approval state.
2. WHEN an approved content version is published, the system SHALL use it for subsequent relevant responses or newly generated documents without silently rewriting previously issued documents.
3. IF content is unapproved, missing or withdrawn, the system SHALL exclude it from authoritative chatbot answers and escalate affected requests where needed.
4. WHEN authorized staff review a past answer or issued document, the system SHALL make its content/template version traceable to support correction and audit.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-04–FR-05, FR-10–FR-11, FR-13, FR-18–FR-19 and FR-21.
- **Assumptions**: AS2–AS3; official course information, FAQs, fees, schedules, PayNow details, financial documents/templates and messaging templates will be supplied later by Q&M. Actual assets, approvers and publication rules remain Q01, Q03, Q05, Q06 and Q12. Q&M owns ongoing content updates after handover. Initial content publication is limited to the certificate course; later course records use the extensible structure specified in FR-04.
- **Source / Objectives**: S1 pp. 10–13; D3 and D10; DR for versioning and approval state; BO1, BO2, BO4.

### Requirement 23: Privacy, Consent and Data Lifecycle (FR-23)

**User Story:** As a participant, I want clear data-use information and controlled handling of my information, so that enrollment and conversation memory respect the approved privacy arrangements.

#### Acceptance Criteria

1. WHEN application conversation memory or lead-data collection begins, the system SHALL apply the privacy notice and any consent or other processing prerequisites agreed with Q&M before retaining that data under the approved process.
2. WHEN enrollment begins, the system SHALL explain the approved purposes for NRIC and DOB collection and record any acknowledgment/consent required by the agreed privacy process before sensitive-field capture.
3. WHILE processing messages, the system SHALL prevent NRIC and DOB collected outside the permitted enrollment boundary from becoming persisted application memory, general lead data or routine log content.
4. WHEN an approved retention period expires for conversation memory, drafts, identity data, screenshots, documents or logs, the system SHALL delete or anonymize the affected data according to the approved schedule and record the lifecycle action.
5. WHEN a participant raises an access, correction, withdrawal or privacy complaint request, the system SHALL route it to the designated privacy owner and record its progress under the approved procedure.
6. IF a model or external service is not approved to process a data category, the system SHALL exclude that category from the service payload and route any dependent work to an approved path.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-02, FR-07, FR-21 and FR-26; NFR-PRI1–NFR-PRI3 and NFR-SEC1–NFR-SEC5.
- **Assumptions**: AS4; PDPA notice wording, retention duration, masking and staff-access policies are Pending confirmation from Mr. Wee/Q&M (Q10–Q11). Q10 also covers collection purpose/necessity, vendor processing, overseas transfers, incident procedures and backup handling. Database-backed memory for Modules A and B across previous days and mandatory enrollment NRIC remain D1/D4; neither establishes a legal basis or a fixed retention period. These criteria specify configurable policy enforcement, not legal conclusions.
- **Source / Objectives**: S1 pp. 10–12; D1, D5 and D11; DR for implementing the eventual approved privacy process; BO4.

### Requirement 24: Deployment and Recovery Readiness (FR-24)

**User Story:** As the Q&M system owner, I want a controlled and recoverable deployment, so that the service can be operated on Q&M-owned infrastructure.

#### Acceptance Criteria

1. WHEN a release is prepared for production, the project team SHALL provide a deployment package for CrewAI coordination, the Intent Classification Agent, all three specialised agents for Modules A–C, database-backed memory for Modules A and B, structured enrollment/payment records, PDF service, staff portals and messaging/email integrations.
2. WHEN production cutover is authorized in the later delivery phase, the project team SHALL configure the Q&M production WhatsApp Business number, DNS, TLS certificate and public webhook and verify inbound/outbound message delivery.
3. WHERE the service runs in production, the system SHALL execute configured automated backups and record backup outcomes for the data and configuration needed for recovery.
4. WHEN a staging recovery exercise is performed, the project team SHALL restore a representative backup and record recovered data, elapsed recovery time and unresolved defects against the approved recovery objectives.
5. IF deployment validation fails, the project team SHALL use the documented rollback/recovery procedure and record the outcome before release acceptance.
6. WHERE a Flask web application is used as the testing prototype, the project team SHALL expose a conversational interface to the same CrewAI workflow and database-backed context, use identified test participants/data, and distinguish prototype results from production WhatsApp verification and integration evidence.

#### Additional Details

- **Priority**: High
- **Complexity**: High
- **Dependencies**: FR-21, FR-23, FR-25–FR-26; NFR-REL1–NFR-REL4.
- **Assumptions**: AS1 and AS5; Q13 and Q15 cover Q&M service targets, infrastructure provision, onboarding and release arrangements. CrewAI is confirmed, the LLM is configurable, and a Flask conversation prototype is permitted under D12. Deployment and restore validation remain future acceptance work.
- **Source / Objectives**: S1 pp. 9–12; D1, D9 and D12; DR for rollback evidence; BO4.

### Requirement 25: Monitoring, Alerts and Support Reporting (FR-25)

**User Story:** As the service operator, I want actionable monitoring and post-launch reporting, so that failures and quality problems can be addressed promptly.

#### Acceptance Criteria

1. WHILE the service is operating, the system SHALL monitor availability, workflow failures, message/email delivery, payment-review queues, backup results and provider usage/cost indicators without placing sensitive payloads in routine logs.
2. WHEN an approved alert condition occurs, the system SHALL notify the configured responsible staff and record the alert and acknowledgement state.
3. WHEN a scheduled KPI reporting milestone occurs after launch, the system and designated reporting owner SHALL produce the agreed measurements and supporting denominators, identifying unavailable data instead of claiming a result.
4. WHEN production support begins, the project team SHALL maintain issue and resolution records for the agreed 30-day support period on delivered application functions.
5. IF a required integration is unavailable, the system SHALL expose the affected workflow and recovery status to staff rather than silently drop accepted work.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-09, FR-14–FR-21, FR-23–FR-24 and FR-26.
- **Assumptions**: AS3 and AS5; Q13–Q16 cover alert thresholds, support commitments, report ownership and the 8-week report beyond 30-day support.
- **Source / Objectives**: S1 pp. 9–13; DR for actionable failure visibility; BO1–BO4.

### Requirement 26: Documentation, Training and Handover (FR-26)

**User Story:** As the Q&M service owner, I want usable documentation and staff training, so that operations and accounts can run the system after project handover.

#### Acceptance Criteria

1. WHEN the delivery package is prepared, the project team SHALL provide architecture/data-flow documentation covering CrewAI, the four agent roles, Module A/B database memory and course extensibility, together with integration configuration guidance, an operations run-book, staff user guides, a content-update guide, backup/restore procedures and a PDPA evidence dossier.
2. WHEN training is scheduled for the later delivery phase, the project team SHALL deliver one operations-team session covering chatbot behavior, dashboard, escalations and content updates, and one accounting-team session covering review, reports, receipts and credit notes.
3. WHEN handover is reviewed, the project team SHALL demonstrate the documented operational tasks and provide attendance records, materials, unresolved issues, system ownership and support contacts.
4. WHEN configuration and access ownership are transferred, the project team SHALL use an approved secure transfer process and document Q&M ownership without placing secrets in ordinary documentation.
5. IF documentation, training, audit evidence or ownership acceptance is missing, the project team SHALL record the outstanding item and leave the corresponding handover acceptance criterion incomplete.

#### Additional Details

- **Priority**: High
- **Complexity**: Medium
- **Dependencies**: FR-20–FR-25 and the Success Criteria section.
- **Assumptions**: AS3 and AS5; named recipients, training dates, handover acceptance and support contacts require Q16. Design and task documents will be prepared later using S2; they are not asserted to exist here.
- **Source / Objectives**: S1 pp. 11–12; S2 pp. 2–4; D1, D3 and D9–D12; BO4.

## Non-Functional Requirements

These criteria define future verification obligations. Numerical targets absent from S1 remain unresolved; a criterion depending on such a target is not fully testable until its referenced question is answered. Security/privacy controls below are proposed engineering requirements derived from S1, not a completed legal assessment or invented Q&M policy.

### Performance Requirements

- **NFR-PER1**: WHEN the system processes the approved normal and peak workload, the system SHALL meet the agreed response-time percentile and throughput targets for FAQ replies, enrollment processing and screenshot acknowledgement. Workload, percentile and targets: Q13.
- **NFR-PER2**: WHEN an enrollment or payment state is committed, the system SHALL make it visible in the staff portals within the approved freshness target. Target: Q13.
- **NFR-PER3**: WHEN an external provider delays processing, the system SHALL distinguish received/pending work from completed work and record elapsed processing time for monitoring.

### Security Requirements

- **NFR-SEC1**: WHEN staff access protected interfaces, the system SHALL authenticate them and enforce the approved role permissions on both displayed actions and backend operations. Password-protected accounting access is required by S1; exact staff authentication/session controls are Q11.
- **NFR-SEC2**: WHEN participant or financial information is transmitted or stored by the application, the system SHALL protect it with encrypted transport and encryption at rest, including database records, payment evidence and backups.
- **NFR-SEC3**: WHEN an inbound webhook requests an operation, the system SHALL validate its provider authenticity and reject invalid requests before disclosing records or changing state. A phone number typed in message text is not equivalent to the verified WhatsApp sender identity.
- **NFR-SEC4**: WHILE credentials or API keys are in use, the system SHALL restrict access to authorized services/operators and exclude secrets, full NRIC, DOB and raw payment evidence from routine logs, source code and general documentation.
- **NFR-SEC5**: WHEN an access-control decision, sensitive record access, staff change, payment verdict or financial-document action occurs, the system SHALL record a protected audit event containing actor/source, time, record reference and outcome, without copying unnecessary sensitive payloads.
- **NFR-SEC6**: IF participant text, retrieved content or an attachment instructs the AI to bypass permissions or financial rules, the system SHALL treat it as untrusted input and enforce the same authorization, validation and payment-review requirements.
- **NFR-SEC7**: WHEN a file is processed as payment evidence, the system SHALL handle it as untrusted content and prevent executable content from being run; inability to safely process an image SHALL be visible as a staff-review issue, not a new business screenshot quota.

### Privacy and PDPA Requirements

- **NFR-PRI1**: WHILE the system retains conversation memory, enrollment information or payment evidence, the system SHALL apply the approved purpose, access and retention rules to each data category rather than assume indefinite retention.
- **NFR-PRI2**: WHEN information is displayed or exported, the system SHALL restrict fields to those required for the authorized task and apply the approved NRIC/DOB masking and document-display rules.
- **NFR-PRI3**: WHEN a production release is reviewed, the project team SHALL provide evidence of approved notices and processing purposes, vendor/data-flow review, retention and deletion configuration, access controls and incident procedures in the PDPA dossier.

PDPA notice wording, retention duration, masking and staff-access policies are **Pending confirmation from Mr. Wee/Q&M** (Q10–Q11). The agreed rules will govern the relevant criteria throughout this document. Q10 also covers collection purpose/necessity, rights-handling process, provider retention, cross-border processing, backups and incident responsibilities. No retention duration, mandatory masking pattern, legal consent basis, geographic hosting rule, breach deadline or compliance certification is asserted here. Memory across previous days remains a confirmed functional requirement; the applicable retention window must be agreed before privacy-dependent production acceptance. D4 and D5 remain the enrollment-field and collection-boundary requirements.

### Usability Requirements

- **NFR-USE1**: WHEN a participant encounters a missing or invalid field, the system SHALL name the issue, explain the next action and retain other valid draft information permitted by the privacy rules.
- **NFR-USE2**: WHERE a participant uses WhatsApp on a mobile device, the system SHALL present course choices, enrollment prompts and payment/review outcomes in readable messages that do not require portal access.
- **NFR-USE3**: WHEN a workflow is pending or fails, the system SHALL distinguish the pending/failed step from completed milestones and offer the available correction or staff-help action.
- **NFR-USE4**: WHERE staff portals support the approved browser and accessibility profile, the system SHALL meet that profile for navigation, form labels, error presentation and keyboard operation. Required browsers, devices, languages and accessibility standard: Q17.
- **NFR-USE5**: WHEN participant usability is evaluated, the system SHALL allow the complete enquiry-to-enrollment and payment/status/document-request journey through natural-language conversation and the supported attachment/email channels without requiring slash-command knowledge or a separate enrollment form.

### Reliability Requirements

- **NFR-REL1**: IF a webhook, job or delivery callback is repeated, the system SHALL process it idempotently so that the same operation does not create duplicate enrollment or financial effects.
- **NFR-REL2**: IF a workflow fails between recording a payment and issuing a receipt, the system SHALL preserve the committed payment and resume only the outstanding work under the approved retry procedure.
- **NFR-REL3**: WHEN a dependency recovers from failure, the system SHALL resume accepted recoverable work without losing its recorded status or bypassing staff-review requirements.
- **NFR-REL4**: WHEN a backup restore is evaluated, the recovered service SHALL meet the approved recovery point objective and recovery time objective; backup frequency, recovery objectives and availability target are Q13 and Q15.

S1's around-the-clock chatbot intent is retained. It does not establish a numerical uptime commitment or 24-hour human staffing.

### Maintainability and Operational Requirements

- **NFR-OPS1**: WHEN requirements, configuration, content or workflow logic change, the project team SHALL keep a versioned change record linking the change to affected requirements and validation evidence.
- **NFR-OPS2**: WHEN an operator investigates a failure, the system SHALL expose correlated workflow/event references and actionable error details without revealing secrets or unnecessary personal data.
- **NFR-OPS3**: WHEN a release or handover is prepared, the project team SHALL document external dependencies, configuration, deployment/recovery steps and known limitations sufficiently for the designated operator to repeat the documented procedures.
- **NFR-OPS4**: WHEN a later course is added through the extensible course model, the system SHALL keep course-specific information and related records separate without requiring replacement of the core enrollment workflow or database schema.
- **NFR-OPS5**: WHEN an approved configurable LLM is substituted, the system SHALL preserve the CrewAI coordination, four agent responsibilities, database-backed memory contract and required permission/validation boundaries.

NFR trace sources: performance and reliability derive from S1 pp. 3, 8–12 and DR; security and privacy derive from S1 pp. 4, 10–12, D5/D8/D11 and DR; usability derives from S1 pp. 2–3, 14–17, D1/D2/D4/D12 and DR; maintainability derives from S1 pp. 11–13, S2 pp. 2–4 and D1/D3/D9. NFRs principally support BO4, with performance/usability also supporting BO1–BO3. NFR-USE5, NFR-OPS4 and NFR-OPS5 trace specifically to the supervisor-confirmed conversational, extensibility and CrewAI/configurable-LLM decisions.

## Constraints and Assumptions

### Technical Constraints

- **TC1 — Channels and interaction**: The production participant entry point is Q&M's WhatsApp Business Cloud API number, using natural-language conversation as the main interaction method. Email supports invoices, instructions, receipts, credit notes and screenshot intake. Slash commands are optional testing/development shortcuts only; no separate participant enrollment form is required.
- **TC2 — Confirmed coordination and memory**: CrewAI is required to coordinate the Intent Classification Agent, FAQ/Enquiry Agent, Enrollment Agent and Payment Verification Agent. Modules A and B require database-backed conversation history and context across messages and previous days. The exact LLM remains configurable. The database and workflow must support adding courses later while the initial release offers the 2-Day Basic Certificate in Dental Assisting. S1's n8n coordination and fixed-model examples are superseded; CrewAI is not an assumption or open platform decision.
- **TC3 — External integration boundary**: No direct Singpass/SkillsFuture government API, bank/payment gateway or existing Q&M accounting-system integration is in the stated scope. Email screenshot intake and internal accounting reports remain included.
- **TC4 — Platform limits**: WhatsApp and email provider limits and messaging rules apply. D6 forbids additional business limits on screenshot submissions. Values and provider behavior must be verified during integration design, not inferred from mockups.
- **TC5 — Prototype and environment separation**: A Flask web application may provide the conversational testing prototype using the confirmed agents and database-backed context. Development/staging must be distinguishable from production in credentials, recipients, identities and data. Q&M's production/staging WhatsApp access and onboarding arrangements remain Q15. Prototype permission does not make a separate participant form mandatory or replace production WhatsApp acceptance.
- **TC6 — Pending data dependencies**: Q&M will provide official course information, FAQs, fees, schedules, PayNow information, invoices, receipts, credit-note templates and messaging templates later. Receipt and approval of the actual materials, privacy rules and staff-access configuration remain prerequisites for their dependent production functions.

### Design Choices Within the Confirmed Architecture

CrewAI coordination, the four agent roles, database-backed Module A/B memory, conversational enrollment and future course extensibility are settled working requirements. Selection of the configurable LLM, database engine, PDF renderer, portal framework and supporting deployment components belongs to subsequent design within those requirements. S1 mentions PostgreSQL/Supabase, PDF-service alternatives, SMTP/SendGrid and Next.js/Retool as possible supporting components; these examples do not make any one choice a newly confirmed dependency. Q&M input is still needed for supplied infrastructure, permitted external data processing, accounts, budget and operational targets (Q10, Q13, Q15). These inputs do not reopen the CrewAI decision.

### Business Constraints

- **BC1 — Confirmed working requirements**: D1–D12 govern this draft, including the initial certificate course with future extensibility, natural-language interaction, CrewAI coordination, Module A/B database memory, six-field guided enrollment, delayed NRIC/DOB collection and phone-based normal lookups. The complete document still awaits formal baseline approval.
- **BC2 — Indicative schedule**: S1 proposes 12 weeks: requirements/discovery Weeks 1–2; design Weeks 3–4; development Weeks 5–8; testing/UAT Weeks 9–10; deployment/post-launch Weeks 11–12. It also proposes early Module A UAT at the end of Week 6. Actual kickoff, dates and approvals are Q15. This document is Week 1 work regardless of its calendar date.
- **BC3 — Source estimates**: S1 states S$9,000–S$10,000 project budget with MSG Grant and estimated S$400–S$600 monthly running costs. These are proposal figures, not verified current quotations, approved expenditure or achieved cost limits. Funding, cost ownership and final limits are Q15.
- **BC4 — Content authority**: Official information and templates will arrive later from Q&M. Fees, schedules, subsidy rules, eligibility, company/payment details, documents and messaging content must be approved before production use. No price or policy in a mockup or draft visual becomes business authority by implication.
- **BC5 — Financial oversight**: Mismatched/unreadable screenshots require staff review. Credit notes require accountant approval. No cancellation, refund, tolerance, installment or credit-note threshold is invented by this draft.
- **BC6 — Delivery commitments**: Documentation, operations and accounting training, 30-day support and KPI reports at 4 and 8 weeks after launch are future proposal deliverables. Their owners and acceptance arrangements are Q16.

### Assumptions

| ID | Operational assumption or pending dependency | Consequence if unavailable |
|---|---|---|
| AS1 | Q&M will provide/obtain WhatsApp Business access, staging access, a production number, email intake/sending facilities and required service credentials. | Integration and release dates need revision; unavailable channels must be recorded rather than simulated as deployed. |
| AS2 | Q&M's later provision of official materials is confirmed by D10; delivery dates, actual contents and approval are pending. The materials cover the initial certificate course, FAQs/funding, fees, schedules, PayNow/company UEN/QR, invoices, receipts, credit-note templates and messaging templates. | Affected authoritative answers, invoices and automated decisions remain held or referred to staff until approved materials arrive. |
| AS3 | Operations, accounts and responsible owners will be available to approve rules, review exceptions, perform UAT and attend training. | Exception turnaround and acceptance dates remain unresolved; automation does not assume their authority. |
| AS4 | Participants normally use their own WhatsApp number and supply an email they can access; Q&M will confirm privacy and record-management rules. | Changed/shared-number and email-correction cases use the approved exceptional process; normal requests still follow D8. |
| AS5 | Q&M will nominate infrastructure, support, privacy and content owners for ongoing operation and post-launch reporting. | Production handover and responsibility transfer cannot be marked complete. |

### Exclusions

| ID | Excluded item | Included alternative or boundary |
|---|---|---|
| EX1 | Direct Singpass login, SkillsFuture balance retrieval, government API integration or automated personal claim submission. | Approved MySkillsFuture link and self-service instructions; internal recording of approved funding information. |
| EX2 | Stripe, PayPal or other payment gateways; bank transaction APIs or automated funds movement. | PayNow/SkillsFuture instructions and evidence-based internal payment review. |
| EX3 | Integration with Q&M's existing accounting software or other operating systems. | Internal database, accountant portal and scheduled CSV reports. |
| EX4 | Native mobile applications and a mandatory separate participant enrollment web form/portal. | Conversational WhatsApp enrollment, email and staff portals; a Flask conversational testing prototype is permitted. |
| EX5 | Developer-managed ongoing FAQ/content updates after handover. | Q&M content editor capability, documentation and training remain included. |
| EX6 | Additional live courses in the initial release, mandatory participant slash commands, and a design that cannot add courses later. | Initial 2-Day Basic Certificate in Dental Assisting, natural-language conversation, database-backed Module A/B memory and course extensibility are required. Testing/development shortcuts remain optional. |
| EX7 | Clinical diagnosis, treatment advice, job placement guarantees, course delivery/LMS functionality and new payment methods. | This scope covers training enquiry/enrollment administration and approved descriptions of course/job pathways. These additional services are not specified by S1. |
| EX8 | Indefinite development-team support or automatic extension of 30-day support to cover later reports. | Report ownership beyond the support window requires Q16; the 8-week reporting deliverable remains recorded. |

## Success Criteria

### Definition of Done

#### Week 1 Requirements Artifact

- [x] The document records the supervisor-confirmed working requirements and retains compatible earlier decisions as D1–D12.
- [x] The initial certificate scope, later course extensibility, conversational enrollment, CrewAI roles and Module A/B database memory are specified consistently.
- [x] The draft contains numbered requirements, stories, EARS criteria, NFRs, scope, open questions and traceability.
- [ ] Mr. Wee/Q&M have reviewed and approved the requirements baseline.
- [ ] All blocking business, privacy and service-level questions have been resolved and incorporated.

Checked items concern document preparation only. They do not indicate approval or operational delivery.

#### Future System and Delivery Acceptance

- [ ] All functional acceptance criteria are implemented and supported by recorded validation evidence.
- [ ] Non-functional targets are approved and verified under an agreed workload and environment.
- [ ] CrewAI coordination, all four agent roles, WhatsApp, email, Module A/B database memory, PDF generation and staff portal integration checks pass.
- [ ] End-to-end tests cover enquiry, enrollment, invoice, payment review, receipts and credit notes.
- [ ] Natural-language completion, all six required fields, follow-up questions, confirmation/storage, privacy boundaries and both screenshot channels are tested without participant commands or a separate enrollment form.
- [ ] Module A and B conversations resume correctly across messages, process restarts and previous days within the retention period once approved.
- [ ] The initial certificate course works end to end, and a separate extensibility check demonstrates that later course records can be added without redesigning the core schema/workflow.
- [ ] Any retained testing/development shortcuts meet the same validation and access rules; their absence does not fail participant acceptance.
- [ ] Duplicate events, ambiguous records, failed deliveries, unreadable/mismatched screenshots and unauthorized access are tested.
- [ ] Q&M operations and accounting UAT is completed and accepted.
- [ ] Security and PDPA review/audit findings are documented and required remediations accepted.
- [ ] Production deployment, webhook delivery, monitoring, backup restore and rollback checks pass.
- [ ] Documentation and both training sessions are delivered and accepted.
- [ ] Ownership, access, unresolved issues and support arrangements are handed over and accepted.
- [ ] The 30-day support commitment is fulfilled under the agreed terms.
- [ ] Post-launch KPI results are measured and reported; target attainment is evaluated from evidence.

### Acceptance Metrics

The first four targets are stated in S1 pp. 12–13. No results exist in this requirements phase. Evaluation-set sizes, sampling method, baseline periods and sign-off owners are Q14. A metric with no eligible observations is reported as not measurable, not as a pass.

| ID | Metric and measurement | Target / gate | Status and trace |
|---|---|---|---|
| M01 | Intent classification/routing accuracy: eligible inbound messages correctly classified by the Intent Classification Agent and routed by CrewAI to the appropriate specialist divided by human-labelled messages in the agreed sample; also report per-intent precision/recall and ambiguous-case outcomes. | At least 95% accuracy, from S1, applied to the confirmed architecture. | Not measured; FR-01–FR-03, D9, BO1–BO3. |
| M02 | FAQ answer accuracy: answers judged factually accurate against approved Q&M content divided by evaluated FAQ answers. Unsupported questions and escalation behavior need explicit evaluation cases. | At least 95%, from S1. | Not measured; FR-04–FR-05 and FR-22, BO1. |
| M03 | Invoice/receipt data accuracy: documents with zero errors in applicable name, NRIC, course-date and fee fields divided by audited documents, checking authorized masking against source values. | 100%, from S1; approved templates are Q05 and display/masking rules are Q10. | Not measured; FR-08–FR-11 and FR-18, BO2–BO3. |
| M04 | Payment false-match rate: auto-confirmed payments later found incorrect by accounting reconciliation divided by reconciled auto-confirmed payments in the agreed period. | 0%, from S1; report actual counts and observation period. | Not measured; FR-15–FR-17, BO3. This target does not claim screenshot fraud is impossible. |
| M05 | Conversational enrollment gate: attempt completion with each of the six fields missing/invalid, interrupt and resume the conversation, correct a value and confirm the summary. | Every approved case collects/corrects missing information before completion, blocks premature invoicing and stores only the confirmed valid enrollment; no command format or separate form is required. | Not tested; FR-07–FR-10, D2–D4, D12. |
| M06 | Payment exceptions/channels: exercise matched, mismatched, blurred, unreadable, multiple-payment and repeated evidence through WhatsApp and email. | Every mismatched/unreadable case creates staff review without automatic Paid status; no extra business screenshot quota. | Not tested; FR-14–FR-17, D6–D7. |
| M07 | Privacy and authorization: exercise pre-enrollment sensitive data, cross-user lookup, normal phone-based requests and staff role restrictions. | Every agreed case meets D5/D8 and the approved access/privacy rules. | Not tested or audited; FR-02, FR-07, FR-12, FR-21, FR-23. |
| M08 | Resilience and operation: load, portal freshness, outage recovery, backup restore, delivery recovery and alert handling. | Numerical service targets: Pending confirmation from Mr. Wee/Q&M (Q13). | Not tested; FR-24–FR-25 and NFR-PER/NFR-REL. |
| M09 | Business outcomes: manual handling time, enquiry workload, response time and enrollment conversion versus discovery baselines. | Baselines and improvement targets: Pending confirmation from Mr. Wee/Q&M (Q14). | Not measured; BO1–BO3; no invented percentage reduction. |
| M10 | Handover readiness: review delivery artifacts and staff demonstration/attendance evidence. | All agreed documentation, two training sessions, ownership and support items accepted. | Not delivered or accepted; FR-26, BO4. |
| M11 | Persistent conversational context: resume Module A and Module B conversations on previous-day history and after a process restart, including FAQ interruptions and corrected enrollment fields. | Retrieve the correct participant's permitted database history and current context, resume outstanding steps and prevent cross-user/stale-state leakage; exact retention-window tests await Q10. | Not tested; FR-01–FR-02, FR-07, D1, BO1–BO2 and BO4. |
| M12 | Course scope/extensibility: verify the initial certificate journey and review the course model with a non-production additional-course fixture. | Initial launch supports the 2-Day Basic Certificate in Dental Assisting; later course data can be added without changing the core schema/workflow or mixing existing records. No second live course is required for release. | Not tested; FR-04, FR-09, FR-22, NFR-OPS4, D3, BO2. |

S1 schedules KPI reporting at 4 and 8 weeks post-launch, then monthly. Q14 determines the measurement windows and Q16 determines who supplies later reports, particularly beyond the 30-day support period. Baselines must be collected during discovery; none are claimed here.

## Glossary

| Term | Definition |
|---|---|
| Acceptance criterion / AC | An observable condition used to judge whether a requirement has been satisfied. |
| AI-assisted verification | Extraction/comparison of screenshot information with rules and staff handling for uncertain cases; it does not establish bank settlement independently. |
| Supported course / intake | The 2-Day Basic Certificate in Dental Assisting in the initial MVP / one of its approved start dates; later courses can be added through the extensible data model. |
| Agentic conversation | Natural-language interaction in which coordinated agents use participant context, ask follow-up questions and perform authorized workflow actions. |
| BO / FR / NFR | Business objective, functional requirement and non-functional requirement identifiers. |
| Conversation memory | Database-backed history and current context for Modules A and B, retrieved across messages and previous days; exact retention and PDPA rules remain pending. |
| CrewAI | The confirmed framework coordinating the Intent Classification Agent and three specialised agents; the exact LLM remains configurable. |
| Credit note | An approved accounting document adjusting an invoice; its issuance is distinct from moving refund funds. |
| DOB | Date of birth; mandatory for enrollment and collected only after enrollment starts and privacy prerequisites are met. |
| EARS | Easy Approach to Requirements Syntax; this document uses WHEN/IF/WHILE/WHERE conditions with SHALL obligations. |
| Enrollment draft | Incomplete or unconfirmed information being collected after enrollment starts; it is not a completed enrollment. |
| Idempotency | Repeating the same event or operation does not repeat its business effect. |
| Intent Classification Agent / routing | The agent that determines enquiry/FAQ, enrollment or payment intent, followed by CrewAI routing to the appropriate specialised agent. This implements the routing responsibility described as Intent Router in S1. |
| FAQ/Enquiry Agent | The Module A agent that answers approved course/FAQ questions using permitted conversation history and current context. |
| Enrollment Agent | The Module B agent that guides six-field collection, validation, participant confirmation and database storage through conversation. |
| Payment Verification Agent | The Module C agent that compares screenshot evidence with invoice/payment rules and routes exceptions to staff. |
| Flask prototype | An optional web application exposing the conversational workflow for testing; it is not a mandatory separate participant enrollment form. |
| KPI | Key performance indicator, measured from evidence over an agreed sample or time window. |
| Lead | A person enquiring about courses who has not necessarily completed enrollment. |
| LLM / vision model | A language model or image-capable model used to interpret input; approved rules still control financial and access actions. |
| Module A / B / C | Enquiries and lead nurturing / enrollment and invoicing / payment verification and accounts. |
| MSG Grant | The grant label used in S1's budget statement; expansion, eligibility and approved funding arrangement are Q15. |
| MVP | Minimum viable product; the initial release covers Modules A–C for the 2-Day Basic Certificate in Dental Assisting and includes a design capable of adding courses later. |
| NRIC | National Registration Identity Card identifier; the required enrollment identity field. Accepted validation rules are Q02. |
| OTP | One-time password; no extra OTP is required for normal requests covered by D8. |
| PayNow / UEN | The supported payment method / Unique Entity Number used in approved company payment instructions. |
| PDPA / PII | Singapore's Personal Data Protection Act / personally identifiable information; policy decisions and compliance evidence remain pending. |
| PDF / CSV | Portable Document Format for issued documents / comma-separated values for accounting exports. |
| RPO / RTO | Recovery point objective (allowable data loss interval) / recovery time objective (allowable recovery duration). |
| SDD | Spec-Driven Development: requirements and other explicit specifications precede implementation and guide validation. |
| Slash command | An optional testing/development shortcut if retained; participants are not required to use command syntax. |
| SFC / SkillsFuture | SkillsFuture Credits / the funding context described in approved training guidance; individual entitlement is not inferred from generic FAQs. |
| Singpass / MySkillsFuture | Government identity service / official self-service portal referenced by the proposal; direct integration is excluded. |
| SMTP / TLS / DNS | Email transfer protocol / encrypted transport protocol / domain-name resolution. |
| UAT | User acceptance testing by Q&M operations/accounts; planned for a later phase. |
| Verified WhatsApp number | The sender identity from an authenticated WhatsApp provider event, matched to authorized enrollment records; not a number merely asserted in message text. |
| VPS / PostgreSQL | Virtual private server / a database option mentioned in S1; the mandatory requirement is database-backed records and Module A/B memory. |
| Webhook | A provider event delivered to an application endpoint; independent events can use persisted conversation memory. |

## Traceability

### Source and Objective Coverage

All criteria under an FR inherit its source/objective mapping and can be referenced individually through its AC number. Design components and executable test-case IDs are intentionally not invented in Week 1; later design/tasks and tests must link back to these identifiers.

| Source / decision | Requirements and supporting sections | Future validation evidence |
|---|---|---|
| S1 pp. 1–4: manual enquiry, enrollment and accounting problem | BO1–BO4; FR-04–FR-20 | End-to-end scenario pack and measured manual-work baselines. |
| S1 pp. 5–7: routing and memory; D1 and D9 | FR-01–FR-02; NFR-PRI1; M01, M11 | CrewAI classification/specialist routing, Module A/B database history across messages/previous days, restart, interruption, expiry and cross-user isolation scenarios. |
| S1 pp. 13–17 workflow topics; D2 supersedes participant command requirements | FR-03–FR-05, FR-07–FR-08, FR-12, FR-14, FR-18; NFR-USE5 | Natural-language completion and missing-information cases; optional development-shortcut checks only if retained. |
| D3: initial certificate course and future course extensibility | FR-04, FR-08–FR-10, FR-22; NFR-OPS4; Scope; M12 | Initial certificate journey, unavailable intake/out-of-scope course cases and a non-production extensibility check; no second live course launch requirement. |
| S1 pp. 2–3, 7–8; D4–D5 | FR-07–FR-10, FR-23; NFR-PRI1–NFR-PRI3; M05 | Natural-language intent, continuous follow-up, six-field validation, confirmation/database storage and pre-enrollment sensitive-data/privacy-boundary checks. |
| S1 pp. 2–3, 7, 12: nurturing and escalation | FR-06, FR-13 | Reminder schedule/suppression and staff handoff cases. |
| S1 pp. 3, 8, 12: invoice pipeline | FR-09–FR-11, FR-22 | Approved PDF/data comparison and delivery-failure/retry checks. |
| S1 pp. 3–4, 8–9; D6–D7 | FR-14–FR-17; NFR-SEC7 | Both-channel attachment cases, labelled vision dataset and staff-review decisions. |
| S1 pp. 4, 8–9, 12: accounting and documents | FR-17–FR-20 | Payment/receipt/credit-note reconciliation, approval and nightly-report cases. |
| S1 pp. 14, 17; D8 | FR-12, FR-18; NFR-SEC3 | Verified-number lookup, multiple records, normal resends and unauthorized-number cases. |
| S1 pp. 3–4, 8, 10–12: staff portals/security/privacy; D11 | FR-20–FR-23; NFR-SEC and NFR-PRI groups | Approved notice/retention/masking/access policy, role matrix, protected endpoint checks, audit records and PDPA review evidence; exact policies remain Q10–Q11. |
| S1 pp. 9–12: deployment and operational delivery; D9 and D12 | FR-24–FR-26; NFR-PER, NFR-REL and NFR-OPS groups | CrewAI deployment/restore evidence, optional Flask conversation prototype evidence distinguished from WhatsApp acceptance, alerts, manuals, attendance and handover acceptance. |
| D9: confirmed CrewAI agent architecture and configurable LLM | FR-01, FR-04, FR-07–FR-09, FR-14–FR-15, FR-24, FR-26; TC2; NFR-OPS5 | Four-role coordination and routing checks; configured-LLM compatibility against unchanged behavioral contracts. |
| D10: official Q&M materials to be provided later | Pending Q&M Materials; FR-04–FR-05, FR-10–FR-11, FR-13, FR-18–FR-19, FR-22; TC6; AS2 | Receipt/approval records for official course, financial and messaging assets; unsupported-content and unavailable-template cases. |
| S1 pp. 12–13: success metrics | M01–M04; FR-25; Success Criteria | Later labelled evaluation and post-launch KPI reports with counts/denominators. |
| S1 pp. 9–13: assumptions, schedule, costs and exclusions | TC1–TC6, BC1–BC6, AS1–AS5, EX1–EX8 | Discovery confirmations and approved scope/change records. |
| S2 pp. 1–4; S3 | Entire document structure; FR-26; NFR-OPS1; review checklist | Reviewed requirements baseline followed by linked design, tasks and tests. |

### Dependency and Change Management

1. Obtain and approve Q&M's initial certificate-course materials, pricing, financial/messaging templates, privacy and operating rules before accepting the production functions that rely on them.
2. Specify identity/context and shared records before finalizing module interaction designs; FR dependency lists express shared interfaces, not a strict coding order.
3. Link later design components, tasks and verification results to FR/AC or NFR IDs and maintain those links when decisions change.
4. Record the decision owner, date and affected requirements when an unresolved question is answered. Maintain the requirements baseline through review; do not silently reinterpret source mockups as policy or reopen supervisor-confirmed working requirements as unanswered questions.

## Unresolved Questions

Every entry below has status **Pending confirmation from Mr. Wee/Q&M**. Only outstanding official materials, business/operating inputs and policy/acceptance decisions remain. The initial course scope, future course extensibility, natural-language interaction, optional development shortcuts, CrewAI coordination, Module A/B database memory, six-field conversational enrollment and optional Flask prototype are resolved working requirements recorded in D1–D12. They are not approval questions here. Original question IDs are retained for traceability, with resolved portions removed.

| ID | Information to confirm | Affected requirements / decision needed before | Status |
|---|---|---|---|
| Q01 | Official information and intake schedules for the 2-Day Basic Certificate in Dental Assisting; any Q&M course code, capacity/waitlist rules, intake allocation and publication of unavailable intakes. | FR-04, FR-08–FR-10, FR-22; approved course content and enrollment acceptance. | Pending confirmation from Mr. Wee/Q&M |
| Q02 | Q&M's required NRIC checks, admission/identity validation rules, accepted date conventions and duplicate business-enrollment handling. Draft retention is covered by Q10. | FR-07–FR-09; business validation rules. | Pending confirmation from Mr. Wee/Q&M |
| Q03 | Official FAQ/funding/admission content, fee tables, taxes, approved subsidy evidence and calculations, official self-service instructions and job-pathway wording for the initial certificate course. | FR-04–FR-05, FR-08, FR-10, FR-22; content and invoice acceptance. | Pending confirmation from Mr. Wee/Q&M |
| Q04 | Escalation owners, review staff, notification channel, operating hours, response commitments; reminder clock origin/reset rules, scheduler tolerance, consent/opt-out behavior and approved reminder text. | FR-06, FR-13, FR-16; escalation and reminder activation. | Pending confirmation from Mr. Wee/Q&M |
| Q05 | Official invoices and approved invoice, receipt and credit-note templates; numbering, signing assets/authority, correction and tax/rounding rules; official company UEN and PayNow QR/recipient details. Document masking/display policy is Q10. | FR-10, FR-18–FR-19, FR-22; document/payment assets and accuracy validation. | Pending confirmation from Mr. Wee/Q&M |
| Q06 | Approved email sender/service, delivery-confirmation milestone, retry schedule/ownership, enrollment/payment instruction templates, and SkillsFuture claim support/settlement steps. | FR-05, FR-09–FR-11, FR-18; delivery and settlement design. | Pending confirmation from Mr. Wee/Q&M |
| Q07 | Designated screenshot intake mailbox, email-to-enrollment association process and staff handling of unknown senders. Provider limits will be checked against the selected services during integration design. | FR-14; email intake configuration and authorization. | Pending confirmation from Mr. Wee/Q&M |
| Q08 | Automatic-match confidence and tolerance, required recipient/reference checks, duplicate/reused evidence treatment, partial/over/combined payments, SkillsFuture evidence, reviewer authority, reconciliation and due-date rules. Mismatched/unreadable evidence must go to staff. | FR-15–FR-17, FR-20; automatic payment confirmation and accounting acceptance. | Pending confirmation from Mr. Wee/Q&M |
| Q09 | Cancellation/refund/credit-note eligibility, approval authority and limits, overdue-account handling and financial correction policy. | FR-19–FR-20; credit-note and overdue automation. | Pending confirmation from Mr. Wee/Q&M |
| Q10 | PDPA notice wording and agreed consent/processing approach; exact retention duration for Module A/B history, drafts, identity data, screenshots, documents, logs and backups; NRIC/DOB masking/display rules; collection purpose/necessity, privacy owner, access/correction/withdrawal process, permitted vendor processing and incident procedure. | FR-02, FR-07–FR-08, FR-10–FR-11, FR-23–FR-26; NFR-PRI; policy-dependent acceptance and use of real personal data. | Pending confirmation from Mr. Wee/Q&M |
| Q11 | Q&M staff-access policy and role matrix, authentication/session controls, account provisioning/revocation, shared/changed-number handling and exceptional email/ownership-change procedures. | FR-12, FR-16, FR-20–FR-21; staff access and exceptional record-change design. | Pending confirmation from Mr. Wee/Q&M |
| Q12 | Content/template approvers and publication process; accounting report columns, recipients, run time/timezone and export access rules. | FR-20, FR-22; publishing and report activation. | Pending confirmation from Mr. Wee/Q&M |
| Q13 | Expected normal/peak workload, response-time percentiles/targets, portal freshness, uptime, queue/alert thresholds, backup frequency, RPO and RTO. | FR-21, FR-24–FR-25; NFR-PER/NFR-REL; measurable service acceptance. | Pending confirmation from Mr. Wee/Q&M |
| Q14 | Manual-work baselines, evaluation datasets/sample sizes, label/review owners, KPI measurement windows, additional business targets and acceptance sign-off criteria. | M01–M09, FR-25; test planning and KPI reporting. | Pending confirmation from Mr. Wee/Q&M |
| Q15 | Q&M-provided hosting/infrastructure and service-account constraints, production/staging WhatsApp access and Meta onboarding, kickoff/release dates, operating budget, MSG Grant details and funding approval. | TC5, BC2–BC3, FR-24; infrastructure provision and release planning. | Pending confirmation from Mr. Wee/Q&M |
| Q16 | Named operations/accounts/privacy/support owners, training dates/attendees, handover and UAT signatories, support start/scope/response terms, and responsibility for 4-week, 8-week and monthly reporting beyond 30-day support. | FR-25–FR-26, BC6; handover and post-launch commitments. | Pending confirmation from Mr. Wee/Q&M |
| Q17 | Q&M's required participant languages and staff browser/device/accessibility profile. | FR-03, FR-21; NFR-USE4; interface acceptance. | Pending confirmation from Mr. Wee/Q&M |

### Requirements Approval Readiness

The supervisor-confirmed working direction is recorded. Full baseline approval remains pending because official course/financial/messaging materials, business validation and payment/accounting rules, PDPA notice/retention/masking and staff-access policies, measurable service targets and named acceptance owners are outstanding. Q&M must provide these inputs or explicitly accept their deferral and the affected scope before the complete requirements baseline can be signed off. Later implementation, testing, deployment, training and audit evidence are delivery gates, not work claimed complete or prerequisites to merely reviewing this Week 1 draft.

## Requirements Review Checklist

This checklist records review of the written requirements, not Q&M approval or implementation evidence. Open items remain open where policies, measurements or stakeholder judgment are needed.

### Completeness

- [x] Each numbered requirement has a user story with a role, capability and benefit.
- [x] Each numbered requirement has EARS acceptance criteria and Additional Details.
- [x] Modules A–C, portals, security, PDPA, deployment, documentation, training, monitoring and handover are covered.
- [x] D1–D12 are recorded and reflected in scope, requirements, assumptions, exclusions, glossary, traceability and acceptance planning.
- [x] Non-functional categories and source KPI targets are included.
- [ ] All success criteria have approved measurement parameters; Q13–Q14 remain open.

### Quality

- [x] Requirements use active obligations and distinguish system behavior from project-team delivery obligations.
- [x] Positive, negative, missing-data, exception and recovery scenarios are specified.
- [x] FR-05 contains one copy of each acceptance criterion, numbered consecutively from 1 to 4.
- [x] Confirmed CrewAI/database-memory architecture is distinguished from configurable LLM and other later design choices.
- [x] No instructional template text, sample participant records or unresolved template fields remain.
- [ ] Every criterion is fully executable as a test today; policy-dependent criteria require answers to the referenced questions.

### EARS Format Validation

- [x] WHEN criteria specify events or triggers.
- [x] IF criteria specify conditions or exception states.
- [x] WHILE criteria specify behavior during an ongoing condition.
- [x] WHERE criteria specify a supported context or environment.
- [x] Every numbered functional acceptance criterion and NFR uses SHALL with a named responsible actor.

### Clarity

- [x] Terminology and the lifecycle/status distinctions are defined consistently.
- [x] Memory, command, six-field enrollment, screenshot-review, course-scope and coordination-architecture conflicts are resolved using D1–D12.
- [x] No identified contradiction remains against the confirmed working requirements after document review.
- [x] Unknown Q&M policies use the stated pending-confirmation wording rather than invented values.
- [ ] Mr. Wee/Q&M have confirmed that all wording and derived requirements match business intent.

### Traceability

- [x] Requirements and criteria have stable identifiers and source/objective mappings.
- [x] Dependencies, assumptions, constraints and exclusions are documented.
- [x] Both PDFs, the template and the supervisor-confirmed working requirements are identified as sources.
- [x] Open decisions identify the affected requirements and needed confirmation point.
- [ ] Later design, implementation tasks and executable tests are linked; these artifacts are outside this Week 1 task.

### Phase Integrity

- [x] Document preparation is distinguished from stakeholder acceptance and operational delivery.
- [x] No implementation, testing, deployment, training, audit, handover, support completion or KPI achievement is marked complete.
- [ ] Requirements baseline approved by Mr. Wee/Q&M.
- [ ] System and delivery acceptance completed with evidence in later phases.
