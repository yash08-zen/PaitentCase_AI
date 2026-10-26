import { useState, useEffect, useCallback, useRef } from "react";
import { useStore } from "../state/store";
import apiClient from "../api/client";
import { Empty, Icon, Proto, Source, Tag, Spinner } from "../components/ui";
import { fmtT, parseServerDate } from "../utils/i18n";

const ALLOWED_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".pdf"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

export default function Documents({ go, user }) {
  const isPatientRole = (user?.role || "").toLowerCase() === "patient";
  const { patients, cases, activeId, notify, t, language } = useStore();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [docType, setDocType] = useState("prescription");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [previewUrls, setPreviewUrls] = useState({});
  const [conflictsCount, setConflictsCount] = useState(0);
  const pollingRef = useRef({});

  const p = patients.find((x) => x.id === activeId);
  const c = cases[activeId];

  // Derive numeric backend patient ID
  const patientBackendId =
    p?.backendId ||
    (typeof p?.id === "number"
      ? p.id
      : p?.id?.startsWith("P-")
      ? parseInt(p.id.replace("P-", ""), 10)
      : null);

  const encounterId = c?.encounterId || null;

  // Load documents and conflicts for current patient from live backend
  const loadDocuments = useCallback(async () => {
    if (!patientBackendId) {
      setDocs([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [res, confs] = await Promise.all([
        apiClient.listDocuments({ patientId: patientBackendId }),
        encounterId ? apiClient.listConflicts(encounterId).catch(() => []) : Promise.resolve([]),
      ]);
      const docList = Array.isArray(res) ? res : [];
      setDocs(docList);
      const openConflicts = Array.isArray(confs) ? confs.filter((x) => x.status === "open") : [];
      setConflictsCount(openConflicts.length);
    } catch (err) {
      console.error("Failed to load documents:", err);
      // Non-fatal if offline
    } finally {
      setLoading(false);
    }
  }, [patientBackendId, encounterId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Cleanup polling timers on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingRef.current).forEach((timer) => clearInterval(timer));
    };
  }, []);

  // Poll an unfinished document until status changes to completed/needs_review/failed
  const startPolling = useCallback(
    (docId) => {
      if (pollingRef.current[docId]) return;

      const timer = setInterval(async () => {
        try {
          const ext = await apiClient.getDocumentExtraction(docId);
          if (ext && (ext.status === "completed" || ext.status === "needs_review" || ext.status === "failed")) {
            clearInterval(pollingRef.current[docId]);
            delete pollingRef.current[docId];

            setDocs((prev) =>
              prev.map((d) =>
                d.id === docId
                  ? {
                      ...d,
                      status: ext.status,
                      extracted_text: ext.extracted_text,
                      extracted_fields: ext.extracted_fields,
                      extraction_confidence: ext.extraction_confidence,
                      provenance_label: ext.provenance_label,
                      processed_at: ext.processed_at,
                    }
                  : d
              )
            );

            if (ext.status === "completed") {
              notify("Prescription OCR extraction completed");
            } else if (ext.status === "needs_review") {
              notify("Document processed: Low confidence / review required");
            } else {
              notify("Document processing failed: Upload preserved for manual review");
            }
          }
        } catch {
          // Keep polling until timeout or success
        }
      }, 1500);

      pollingRef.current[docId] = timer;
    },
    [notify]
  );

  // Poll any initial documents that are in pending/processing state
  useEffect(() => {
    docs.forEach((d) => {
      if (d.status === "pending" || d.status === "processing") {
        startPolling(d.id);
      }
    });
  }, [docs, startPolling]);

  // Load preview blob URL for authenticated image display
  const loadPreview = async (docId) => {
    if (previewUrls[docId]) return;
    try {
      const blob = await apiClient.getDocumentFileBlob(docId);
      const url = URL.createObjectURL(blob);
      setPreviewUrls((prev) => ({ ...prev, [docId]: url }));
    } catch (err) {
      console.warn("Could not load preview blob for doc", docId, err);
    }
  };

  // Upload handler for real files
  const handleFileUpload = async (file) => {
    if (!file) return;
    if (!patientBackendId) {
      setUploadError("Please select a registered patient before uploading documents.");
      return;
    }

    // Size check
    if (file.size > MAX_FILE_SIZE) {
      setUploadError(`File exceeds maximum allowed size of 20 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB).`);
      return;
    }

    // Extension check
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      setUploadError(`Unsupported file format '${ext}'. Supported formats: JPEG, PNG, WebP, TIFF, PDF.`);
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const uploadedDoc = await apiClient.uploadDocument(
        patientBackendId,
        file,
        encounterId,
        docType
      );

      setDocs((prev) => [uploadedDoc, ...prev]);
      notify(`Uploaded ${file.name}. OCR engine started in background.`);

      // Begin polling for OCR result
      startPolling(uploadedDoc.id);

      // Attempt to load preview if it is an image
      if (file.type.startsWith("image/")) {
        loadPreview(uploadedDoc.id);
      }
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err.message || "Failed to upload document to server");
    } finally {
      setUploading(false);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  if (!p) {
    return (
      <Empty
        title={t("noPatientSelected")}
        text={t("chooseForDocs")}
        action={
          <button className="btn primary" onClick={() => go(isPatientRole ? "portal" : "patients")}>
            {isPatientRole ? t("portal") : t("openPatientList")}
          </button>
        }
      />
    );
  }

  return (
    <>
      <div className="head">
        <div>
          <h1>{t("docsHeading")}</h1>
          <p className="soft">
            {p.name} · {p.id} {encounterId ? `· ${t("encounter")} #${encounterId}` : ""} · <span className="tag t-sys" style={{ fontSize: "0.72rem" }}><Icon n="check" size={12} /> {t("localNeuralOcr")}</span>
          </p>
        </div>
        <div className="actions">
          <button className="btn out sm" onClick={loadDocuments} disabled={loading}>
            <Icon n="reset" size={14} /> {t("refreshDocs")}
          </button>
          {!isPatientRole && (
            <button className="btn out sm" onClick={() => go("review")}>
              {t("doctorReviewBtn")}
            </button>
          )}
        </div>
      </div>

      {/* Non-Diagnostic Boundary Notice */}
      <div className="clinical-boundary-notice" role="region" aria-label="Clinical Boundary Notice">
        <div className="notice-content">
          <span className="notice-badge">{t("boundaryBadge")}</span>
          <span>
            {language === "hi"
              ? "OCR आउटपुट असत्यापित मशीन निष्कर्षण हैं जिन्हें document_extracted_unverified के रूप में चिह्नित किया गया है। नैदानिक उपयोग से पहले अधिकृत चिकित्सक सत्यापन अनिवार्य है।"
              : language === "mr"
              ? "OCR आउटपुट ही असत्यापित मशीन काढणी आहेत ज्यांना document_extracted_unverified म्हणून टॅग केले आहे. क्लिनिकल वापरापूर्वी अधिकृत डॉक्टरांचे सत्यापन आवश्यक आहे."
              : "OCR outputs are unverified machine extractions tagged as document_extracted_unverified. All extracted text, dosages, and instructions require authorized physician verification before clinical reliance."}
          </span>
        </div>
      </div>

      <div className="cols docs">
        {/* Left Column: Upload Form */}
        <div className="card">
          <h2>{t("uploadDocHeading")}</h2>
          <p className="small soft" style={{ marginTop: 4, marginBottom: 14 }}>
            {t("uploadDocSubheading")}
          </p>

          <label className="fld">
            <span className="small soft">{t("docType")}</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              disabled={uploading}
              aria-label="Document Type"
            >
              <option value="prescription">{t("prescriptionType")}</option>
              <option value="lab_report">{t("labReportType")}</option>
              <option value="discharge_summary">{t("dischargeSummaryType")}</option>
              <option value="other">{t("otherDocType")}</option>
            </select>
          </label>

          {/* Drag & Drop Zone */}
          <label
            className="drop"
            style={{
              opacity: uploading ? 0.6 : 1,
              pointerEvents: uploading ? "none" : "auto",
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files?.[0]) {
                handleFileUpload(e.dataTransfer.files[0]);
              }
            }}
          >
            <Icon n="doc" size={32} />
            <b>{uploading ? t("uploadingDoc") : t("dropZoneText")}</b>
            <span className="small soft">
              {t("dropZoneSubtext")}
            </span>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/tiff,application/pdf"
              hidden
              disabled={uploading}
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
              data-testid="file-upload-input"
            />
          </label>

          {uploading && (
            <div style={{ marginTop: 12 }}>
              <div className="row" style={{ marginBottom: 6 }}>
                <span className="small soft">{t("uploadingDoc")}</span>
                <Spinner size={16} text="" />
              </div>
              <div className="bar">
                <i className="indet" />
              </div>
            </div>
          )}

          {uploadError && (
            <div className="banner bad" role="alert" style={{ marginTop: 12 }}>
              <Icon n="alert" />
              <div>
                <b>{t("uploadFailed")}</b>
                <p className="small">{uploadError}</p>
              </div>
            </div>
          )}

          <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
            <p className="small soft">
              <b>{t("securitySpecs")}</b>
            </p>
            <ul className="small soft" style={{ paddingLeft: 16, margin: "6px 0 0" }}>
              <li>{t("spec1")}</li>
              <li>{t("spec2")}</li>
              <li>{t("spec3")}</li>
              <li>{t("spec4")}</li>
            </ul>
          </div>
        </div>

        {/* Right Column: Uploaded Documents & Real OCR Results */}
        <div>
          {conflictsCount > 0 && (
            <div className="banner bad" role="alert" style={{ marginBottom: 14 }}>
              <Icon n="alert" />
              <div>
                <b>{fmtT(t("nDiscrepanciesDetected"), { n: conflictsCount })}</b>
                <p className="small">
                  {t("docsContradict")}
                </p>
              </div>
              {!isPatientRole && (
                <button className="btn out sm" onClick={() => go("review")}>
                  {t("openDoctorReviewBtn")}
                </button>
              )}
            </div>
          )}

          {loading && docs.length === 0 ? (
            <div className="card" style={{ padding: 40, textAlign: "center" }}>
              <Spinner size={24} text={t("loadingDocs")} />
            </div>
          ) : docs.length === 0 ? (
            <Empty
              title={t("noDocsYet")}
              text={t("noDocsYetText")}
            />
          ) : (
            docs.map((d) => {
              const isProcessing = d.status === "pending" || d.status === "processing";
              const isReview = d.status === "needs_review";
              const isFailed = d.status === "failed";
              const isComplete = d.status === "completed";

              const confidencePct =
                d.extraction_confidence !== null && d.extraction_confidence !== undefined
                  ? Math.round(d.extraction_confidence * 100)
                  : null;

              const elapsedSec = d.extracted_fields?.processing_time_seconds;

              return (
                <div className="card" key={d.id} style={{ marginBottom: 14 }}>
                  <div className="row">
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <h2 style={{ margin: 0 }}>{d.original_filename}</h2>
                        {isProcessing && (
                          <Tag kind="sys">
                            <Spinner size={12} text="" /> {t("processingOcr")}
                          </Tag>
                        )}
                        {isComplete && <Tag kind="ver">{t("ocrComplete")}</Tag>}
                        {isReview && <Tag kind="warn">{t("stNeedsReview")}</Tag>}
                        {isFailed && <Tag kind="bad">{t("failed")}</Tag>}
                      </div>
                      <p className="small soft" style={{ marginTop: 4 }}>
                        {d.document_type.toUpperCase()} · {formatBytes(d.file_size_bytes)} ·{" "}
                        {d.created_at ? parseServerDate(d.created_at).toLocaleString() : t("justNow")}
                      </p>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Source s={d.provenance_label || "document_extracted_unverified"} />
                    </div>
                  </div>

                  {/* Processing Status Banner */}
                  {isProcessing && (
                    <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--shell)", borderRadius: 10 }}>
                      <div className="row" style={{ marginBottom: 6 }}>
                        <span className="small">{t("runningOcr")}</span>
                        <span className="small soft">{t("livePolling")}</span>
                      </div>
                      <div className="bar">
                        <i className="indet" />
                      </div>
                    </div>
                  )}

                  {/* Handwritten / Low-confidence Notice */}
                  {(isReview || (d.extraction_confidence !== null && d.extraction_confidence < 0.70)) && (
                    <div className="banner" data-testid="handwritten-warning-banner" style={{ background: "var(--amberbg)", color: "var(--amber)", marginTop: 12 }}>
                      <Icon n="alert" />
                      <div>
                        <b>{t("lowConfidenceTitle")}</b>
                        <p className="small">
                          {t("lowConfidenceText")}
                        </p>
                      </div>
                    </div>
                  )}

                  {isFailed && (
                    <div className="banner bad" style={{ marginTop: 12 }}>
                      <Icon n="alert" />
                      <div>
                        <b>{t("ocrFailed")}</b>
                        <p className="small">
                          {t("ocrFailedText")}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* OCR Extractions Output */}
                  {d.extracted_text && (
                    <div style={{ marginTop: 14 }}>
                      <div className="row" style={{ marginBottom: 6 }}>
                        <span className="small soft">
                          <b>{t("extractedText")}</b>
                        </span>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          {confidencePct !== null && (
                            <span className="small soft">
                              {t("confidence")}: <b>{confidencePct}%</b>
                            </span>
                          )}
                          {elapsedSec && (
                            <span className="small soft">
                              {t("elapsed")}: <b>{elapsedSec}s</b>
                            </span>
                          )}
                        </div>
                      </div>
                      <pre
                        style={{
                          background: "#f4f7f4",
                          border: "1px solid var(--line)",
                          borderRadius: 10,
                          padding: "10px 14px",
                          fontSize: "0.86rem",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          maxHeight: 220,
                          overflowY: "auto",
                          margin: 0,
                          color: "var(--ink)",
                          fontFamily: "ui-monospace, monospace",
                        }}
                      >
                        {d.extracted_text}
                      </pre>
                    </div>
                  )}

                  {/* Authenticated Preview Actions */}
                  <div className="actions" style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
                    <button
                      className="btn out sm"
                      onClick={() => {
                        loadPreview(d.id);
                        setSelectedDoc(selectedDoc === d.id ? null : d.id);
                      }}
                    >
                      <Icon n="doc" size={14} />
                      {selectedDoc === d.id ? t("hidePreview") : t("viewScan")}
                    </button>
                    {!isPatientRole && (
                      <button className="btn out sm" onClick={() => go("review")}>
                        {t("openDoctorReviewBtn")}
                      </button>
                    )}
                  </div>

                  {/* Expanded Image Preview */}
                  {selectedDoc === d.id && (
                    <div style={{ marginTop: 12, padding: 10, background: "#0000000a", borderRadius: 12, textAlign: "center" }}>
                      {previewUrls[d.id] ? (
                        <img
                          src={previewUrls[d.id]}
                          alt={d.original_filename}
                          style={{
                            maxWidth: "100%",
                            maxHeight: 450,
                            borderRadius: 8,
                            boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
                          }}
                        />
                      ) : (
                        <div style={{ padding: 20 }}>
                          <Spinner size={20} text={t("fetchingFile")} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
