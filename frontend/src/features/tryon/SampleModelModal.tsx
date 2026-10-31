import { useState } from "react";
import Modal from "../../components/ui/Modal";
import { Check, Sparkles, UserRound } from "../../icons";

export interface SampleModel {
  id: "male" | "female";
  label: string;
  gender: "male" | "female";
  description: string;
  previewUrl: string;
  filename: string;
}

export const SAMPLE_MODELS: SampleModel[] = [
  {
    id: "male",
    label: "Male Model",
    gender: "male",
    description: "Athletic male build in neutral studio lighting",
    previewUrl: "/api/samples/person-male",
    filename: "studio-person.jpg",
  },
  {
    id: "female",
    label: "Female Model",
    gender: "female",
    description: "Elegant female build in neutral studio lighting",
    previewUrl: "/api/samples/person-female",
    filename: "vastraview_female_model.png",
  },
];

interface SampleModelModalProps {
  open: boolean;
  onClose: () => void;
  onSelectModel: (model: SampleModel) => void;
  currentFilename?: string;
  loading?: boolean;
}

export default function SampleModelModal({
  open,
  onClose,
  onSelectModel,
  currentFilename,
  loading = false,
}: SampleModelModalProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <Modal wide open={open} onClose={onClose} title="Choose a Sample Model">
      <div style={{ padding: "4px 0 16px 0" }}>
        <p style={{ margin: "0 0 20px 0", color: "#64748b", fontSize: "14px" }}>
          Select a professional studio model to preview and test virtual try-ons instantly.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "24px",
            marginBottom: "16px",
          }}
        >
          {SAMPLE_MODELS.map((model) => {
            const isSelected =
              currentFilename === model.filename ||
              (model.id === "male" && currentFilename === "original-person.png");
            const isHovered = hoveredId === model.id;

            return (
              <div
                key={model.id}
                role="button"
                tabIndex={0}
                aria-label={`Select ${model.label}`}
                onClick={() => {
                  if (!loading) {
                    onSelectModel(model);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    if (!loading) onSelectModel(model);
                  }
                }}
                onMouseEnter={() => setHoveredId(model.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  background: isSelected ? "#f4f8f5" : "#ffffff",
                  borderRadius: "16px",
                  border: isSelected
                    ? "2px solid #1e3a2b"
                    : isHovered
                    ? "2px solid #8fa89b"
                    : "2px solid #e2e8f0",
                  boxShadow: isSelected
                    ? "0 8px 24px rgba(30, 58, 43, 0.16)"
                    : isHovered
                    ? "0 10px 24px rgba(0, 0, 0, 0.08)"
                    : "0 4px 12px rgba(0, 0, 0, 0.04)",
                  transform: isHovered && !loading ? "translateY(-4px)" : "none",
                  transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                  cursor: loading ? "wait" : "pointer",
                  overflow: "hidden",
                  position: "relative",
                  outline: "none",
                }}
              >
                {/* Active selection badge */}
                {isSelected && (
                  <div
                    style={{
                      position: "absolute",
                      top: "12px",
                      right: "12px",
                      background: "#1e3a2b",
                      color: "#ffffff",
                      borderRadius: "999px",
                      padding: "4px 10px",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                      fontSize: "12px",
                      fontWeight: 600,
                      zIndex: 2,
                      boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
                    }}
                  >
                    <Check size={14} /> Active
                  </div>
                )}

                {/* Model preview image container */}
                <div
                  style={{
                    position: "relative",
                    width: "100%",
                    height: "320px",
                    background: "#f8fafc",
                    overflow: "hidden",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <img
                    src={model.previewUrl}
                    alt={model.label}
                    loading="lazy"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "contain",
                      objectPosition: "center top",
                      transition: "transform 0.3s ease",
                      transform: isHovered ? "scale(1.03)" : "scale(1)",
                    }}
                  />
                </div>

                {/* Card footer details */}
                <div
                  style={{
                    padding: "16px 18px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    flex: 1,
                    justifyContent: "space-between",
                    background: isSelected ? "#f4f8f5" : "#ffffff",
                  }}
                >
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        fontWeight: 700,
                        fontSize: "16px",
                        color: "#1e3a2b",
                      }}
                    >
                      <UserRound size={16} />
                      {model.label}
                    </div>
                    <p
                      style={{
                        margin: "4px 0 0 0",
                        fontSize: "12.5px",
                        color: "#64748b",
                        lineHeight: 1.4,
                      }}
                    >
                      {model.description}
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={loading}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!loading) onSelectModel(model);
                    }}
                    style={{
                      marginTop: "10px",
                      padding: "8px 16px",
                      borderRadius: "8px",
                      fontSize: "13px",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "6px",
                      border: "none",
                      cursor: loading ? "wait" : "pointer",
                      background: isSelected ? "#1e3a2b" : isHovered ? "#284e3a" : "#f1f5f9",
                      color: isSelected || isHovered ? "#ffffff" : "#1e293b",
                      transition: "all 0.2s ease",
                    }}
                  >
                    {isSelected ? (
                      <>
                        <Check size={15} /> Selected
                      </>
                    ) : (
                      <>
                        <Sparkles size={14} /> Select {model.label}
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            paddingTop: "8px",
            borderTop: "1px solid #f1f5f9",
          }}
        >
          <button
            type="button"
            className="button secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
