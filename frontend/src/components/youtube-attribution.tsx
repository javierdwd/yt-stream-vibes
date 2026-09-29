type Props = {
  className?: string;
  /** Visual height in CSS px. Use 20 | 24 | 28 | 32 (have matching @2x assets). */
  height?: 16 | 20 | 24 | 28 | 32;
};

/** Ink-tight master is 500×65. */
const ASPECT = 160 / 24;

const SRC: Record<16 | 20 | 24 | 28 | 32, string> = {
  16: "/branding/developed-with-youtube-20@2x.png",
  20: "/branding/developed-with-youtube-20@2x.png",
  24: "/branding/developed-with-youtube-24@2x.png",
  28: "/branding/developed-with-youtube-28@2x.png",
  32: "/branding/developed-with-youtube-32@2x.png",
};

/**
 * Official “Developed with YouTube” attribution.
 * @see https://developers.google.com/youtube/terms/branding-guidelines
 */
export function YoutubeAttribution({ className, height = 16 }: Props) {
  const width = Math.round(height * ASPECT);

  return (
    <a
      href="https://www.youtube.com"
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex shrink-0 items-center opacity-80 transition-opacity duration-200 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none ${className ?? ""}`}
      title="Developed with YouTube"
      aria-label="Developed with YouTube"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={SRC[height]}
        alt="Developed with YouTube"
        width={width}
        height={height}
        draggable={false}
        style={{
          width: `${width}px`,
          height: `${height}px`,
          maxWidth: "none",
        }}
      />
    </a>
  );
}
