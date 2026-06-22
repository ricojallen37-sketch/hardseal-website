# Paid-Work Intake Checklist

**Drafting aid for attorney review. Not legal advice.** This file is an
operational shield for paid and CUI-adjacent work. It does not replace a
lawyer, insurance, CMMC counsel, export-control review, or privacy counsel,
and it cannot prevent a claim from being filed. Do not start paid customer
implementation, production analysis, CUI review, evidence ingestion, or any
regulated-data handling until the customer has accepted the MSA / SOW / DPA
language and the data-category table below is complete.

Ground truth this checklist reflects:

- **CUI** (NARA, <https://www.archives.gov/cui/about>): information that
  requires safeguarding or dissemination controls under law, regulation, or
  government-wide policy, and is not classified. The CUI program affects
  organizations that handle, possess, use, share, or receive CUI, or operate /
  use / access federal information or systems on behalf of an agency.
- **DFARS 252.204-7012**
  (<https://www.acquisition.gov/dfars/252.204-7012-safeguarding-covered-defense-information-and-cyber-incident-reporting>):
  requires adequate security for covered defense information (CDI), NIST SP
  800-171 on covered contractor systems, cyber-incident reporting to DoD within
  72 hours of discovery, 90-day preservation of images and monitoring data
  after the report, FedRAMP Moderate-equivalent treatment for external cloud
  services handling CDI, and flow-downs for CDI and operationally critical
  support.

---

## 1. Data-category authorization table (attach to every SOW)

| Data category | Authorized? | Delivery method | Environment | Notes |
|---|---:|---|---|---|
| Public / sample / synthetic data | Yes / No | | | |
| Customer confidential business data | Yes / No | | | |
| Personal data | Yes / No | | | |
| CUI | Yes / No | | | |
| Covered defense information (CDI) | Yes / No | | | |
| Export-controlled technical data (ITAR / EAR) | Yes / No | | | |
| Credentials / secrets | **No by default** | | | |
| Incident / vulnerability data | **No by default** | | | |

**Customer representation (place immediately below the table):**

> Customer represents that the table above accurately identifies the data
> categories authorized for this SOW. Any category not marked "Yes" is outside
> scope and must not be provided to Hardseal.

---

## 2. Proposal / invoice footer

Use on every proposal, quote, invoice, and email that attaches a deliverable:

> Hardseal deliverables are evidence-integrity and readiness aids only. They are
> not legal advice, CMMC certification, C3PAO assessment, Cyber AB endorsement,
> DoD approval, FedRAMP authorization, SPRS submission, or a guarantee of
> regulatory outcome. Do not send CUI, CDI, export-controlled data, credentials,
> incident data, or production secrets unless authorized by a signed SOW.

---

## 3. Customer email intake scripts

**When a customer wants to send evidence (SSP, POA&M, screenshots, SPRS score, CUI examples):**

> Please do not email CUI, CDI, export-controlled technical data, credentials,
> production secrets, incident data, or sensitive vulnerability data. For now,
> please send sanitized examples or synthetic / sample artifacts only. If you
> need Hardseal to handle regulated data, we need a signed SOW / DPA first that
> identifies the data category, delivery method, environment, and incident
> process.

**When a customer asks if Hardseal makes them compliant:**

> Hardseal helps produce and verify evidence-integrity / readiness artifacts. It
> does not certify compliance, replace a C3PAO, submit SPRS scores, provide legal
> advice, or guarantee assessor acceptance. Your compliance status depends on
> your actual controls, systems, contracts, evidence, personnel, and assessor
> judgment.

**When a customer asks about DFARS incidents:**

> Hardseal is not your official DIBNet reporter unless a signed SOW expressly
> assigns that task. If a signed CUI / CDI SOW exists and Hardseal becomes aware
> of a suspected incident involving Customer Data in Hardseal-controlled systems,
> Hardseal will notify your designated contact and cooperate with your reporting
> and preservation process.

---

## 4. Minimum MSA / SOW / DPA clause modules

Concise form. Expand with counsel before execution.

### Scope and no implied services
> Hardseal will provide only the services expressly described in the applicable
> SOW. No regulated-data handling, compliance attestation, official reporting,
> legal advice, certification support, CMMC assessment, SPRS submission,
> incident-response service, managed security service, or continuous monitoring
> is included unless expressly stated in the SOW.

### Customer environment
> Unless the SOW says otherwise, Hardseal products and deliverables operate in
> the Customer-controlled environment, and Customer Data will not be transmitted
> to or stored in Hardseal-controlled systems.

### Customer duties
> Customer is responsible for: (a) identifying, classifying, marking, and
> segregating Customer Data; (b) determining whether Customer Data includes CUI,
> CDI, export-controlled technical data, personal data, or other regulated data;
> (c) ensuring Customer's systems, users, configurations, access controls, and
> use of the Services comply with Customer's contracts and laws; (d) maintaining
> backups; (e) reviewing all Hardseal outputs before reliance; and (f) making all
> official submissions, certifications, reports, and representations to
> government agencies, assessors, primes, customers, auditors, and regulators
> unless the SOW expressly states otherwise.

### CUI authorization
> Customer may provide CUI, CDI, or export-controlled technical data only if the
> SOW expressly authorizes that data category. Customer will not provide such
> data by email, public web forms, public verifier inputs, public downloads, or
> any channel not specified in the SOW.

### DFARS incident cooperation
> If the SOW authorizes CDI or DFARS-covered work, the parties will maintain
> named security contacts. Hardseal will notify Customer without undue delay
> after becoming aware of a suspected Security Incident involving Customer Data
> in Hardseal-controlled systems. Customer remains responsible for determining
> whether an event is reportable and for making any required government,
> prime-contractor, assessor, regulator, or third-party notifications unless the
> SOW expressly assigns a reporting task to Hardseal. Hardseal will provide
> reasonable cooperation, information, and preservation support within its
> control.

### Preservation
> For DFARS-covered work, Hardseal will preserve relevant records, logs, images,
> monitoring data, and evidence within its possession or control for the period
> specified in the SOW or required by applicable flow-down terms (at least the
> DFARS 90-day window where it applies). Hardseal is not responsible for
> preserving systems, logs, packet capture, or records outside its possession or
> control.

### Cloud / subprocessor
> Hardseal will not use an external cloud service provider to store, process, or
> transmit Customer Data identified in the SOW as CUI or CDI unless the SOW
> identifies the provider and the required security baseline or flow-down terms
> (FedRAMP Moderate-equivalent where DFARS applies). Customer is responsible for
> approving any customer-selected environment or provider.

### Warranty disclaimer
> Hardseal does not warrant that the Services will make Customer compliant,
> prevent cyber incidents, satisfy an assessor, obtain certification, avoid audit
> findings, avoid breach notification, avoid contract remedies, or satisfy all
> obligations applicable to Customer.

### Limitation of liability
> Except for excluded claims, each party's total aggregate liability arising out
> of or relating to the agreement will not exceed the fees paid or payable to
> Hardseal under the applicable SOW during the twelve months before the event
> giving rise to the claim. Neither party is liable for indirect, incidental,
> special, consequential, exemplary, punitive, lost-profit, lost-revenue,
> lost-data, business-interruption, reputational, procurement-delay,
> certification-delay, or contract-loss damages.

### Excluded claims
> The cap does not apply to Customer's payment obligations; Customer's
> unauthorized disclosure or misuse of Hardseal IP; Customer's use of the
> Services in violation of law; Customer's provision of regulated data outside
> the authorized SOW; Customer's misrepresentation of Hardseal artifacts as
> certification or official approval; or either party's fraud, willful
> misconduct, or gross negligence to the extent liability cannot be limited by
> law.

### Indemnity (Customer)
> Customer will indemnify and defend Hardseal from claims arising from: (a)
> Customer's data, systems, instructions, classifications, or configurations; (b)
> Customer's provision of CUI, CDI, export-controlled data, personal data,
> credentials, or other regulated data outside the authorized scope; (c)
> Customer's official submissions, certifications, government-contract
> representations, SPRS entries, incident reports, or assessor communications;
> (d) Customer's misuse or misrepresentation of Hardseal artifacts; or (e)
> Customer's violation of law, contract, or third-party rights.

### DPA: processing instructions
> Hardseal will process Customer Personal Data only to provide the Services and
> only per Customer's documented instructions in the agreement, SOW, and DPA.

### DPA: breach timing
> Hardseal will notify Customer without undue delay after becoming aware of a
> Security Incident involving Customer Personal Data in Hardseal-controlled
> systems, describing (to the extent known) the nature, affected data, likely
> consequences, mitigation steps, and a follow-up contact.

### DPA: deletion / return
> Upon termination or written request, Hardseal will delete or return Customer
> Data in its possession or control within 30 days unless the SOW requires a
> different period, retention is required by law, or retention is reasonably
> necessary for dispute, security, audit, or legal-hold purposes.

---

## 5. Minimum website / intake checklist

1. "No regulated data by default" is in the public Terms.
2. "Public channels are not regulated-data channels" is in the Privacy Policy.
3. Verifier reliance language is narrowed (no broad "free of accidental change"
   promise; "no detected hash / schema / chain mismatch under published logic").
4. "Not a C3PAO / RPO / Cyber AB / DoD / legal opinion / SPRS submitter"
   disclaimer is explicit in Terms.
5. Customer classification responsibility is in Terms.
6. Public-to-paid liability bridge is in Terms.
7. Last Updated dates on Terms and Privacy are current.
8. "Do not send CUI / CDI / secrets through public channels" appears near
   contact surfaces and the verifier input.
9. A signed SOW is required before any paid pilot involving customer evidence.
10. The data-category authorization table (Section 1) is completed before any
    paid customer work begins.
