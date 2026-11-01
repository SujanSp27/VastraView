import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "../../icons";

function ShirtIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z" />
    </svg>
  );
}

function TapeMeasureIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 17.5A3.5 3.5 0 0 0 7.5 21H18a4 4 0 0 0 4-4V7a4 4 0 0 0-4-4H7.5A3.5 3.5 0 0 0 4 6.5" />
      <path d="M4 10h5" />
      <path d="M4 14h3" />
      <circle cx="14" cy="12" r="3" />
      <path d="M14 12v3" />
    </svg>
  );
}

function TagIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z" />
      <path d="M7 7h.01" />
    </svg>
  );
}

export default function HomePage() {
  return (
    <section className="hero-studio" aria-label="Virtual Fitting Studio">
      <div className="hero-studio-container">
        {/* Left Column: Editorial Headline, Description, CTAs, Highlights */}
        <div className="hero-content-col">
          <div className="hero-eyebrow">
            <span className="hero-eyebrow-text">THE VIRTUAL FITTING STUDIO</span>
            <span className="hero-eyebrow-bar" />
          </div>

          <h1 className="hero-headline">
            <span className="hero-headline-line">Your Style.</span>
            <span className="hero-headline-line">Your Fit.</span>
            <em className="hero-headline-accent">Your Confidence.</em>
          </h1>

          <p className="hero-description">
            Try outfits virtually, get brand-specific size recommendations, and
            discover styles that suit you.
          </p>

          <div className="hero-actions">
            <Link to="/catalog" className="hero-btn hero-btn-primary">
              <ShirtIcon size={18} />
              <span>Discover Styles</span>
              <ArrowRight size={16} />
            </Link>
            <Link to="/tryon" className="hero-btn hero-btn-secondary">
              <Sparkles size={16} />
              <span>Virtual Try-On</span>
            </Link>
          </div>

          <div className="hero-features-row" role="list">
            <div className="hero-feature-item" role="listitem">
              <div className="hero-feature-icon">
                <TapeMeasureIcon size={20} />
              </div>
              <div className="hero-feature-text">
                <strong>Smart Sizing</strong>
                <span>Get your right size</span>
              </div>
            </div>

            <div className="hero-feature-divider" aria-hidden="true" />

            <div className="hero-feature-item" role="listitem">
              <div className="hero-feature-icon">
                <ShirtIcon size={20} />
              </div>
              <div className="hero-feature-text">
                <strong>Virtual Try-On</strong>
                <span>See it on you instantly</span>
              </div>
            </div>

            <div className="hero-feature-divider" aria-hidden="true" />

            <div className="hero-feature-item" role="listitem">
              <div className="hero-feature-icon">
                <TagIcon size={20} />
              </div>
              <div className="hero-feature-text">
                <strong>Curated Styles</strong>
                <span>Explore top brands</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Dual Fashion Model Photography */}
        <div className="hero-image-col">
          <div className="hero-image-wrapper">
            <picture>
              <source
                srcSet="/editorial/hero-fashion-models.webp 1x, /editorial/hero-fashion-models@2x.webp 2x"
                type="image/webp"
              />
              <img
                src="/editorial/hero-fashion-models.png"
                srcSet="/editorial/hero-fashion-models.png 1x, /editorial/hero-fashion-models@2x.png 2x"
                alt="VastraView male and female models in modern coordinated fashion outfits"
                className="hero-models-img"
                width={464}
                height={476}
                fetchPriority="high"
                loading="eager"
              />
            </picture>
          </div>
        </div>
      </div>
    </section>
  );
}
