import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  BrainCircuit,
  CalendarCheck,
  ChevronLeft,
  ChevronRight,
  MessagesSquare,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";

type HomeFeatureSlide = {
  image: string;
  imageAlt: string;
  icon: LucideIcon;
  title: string;
  description: string;
};

const AUTO_PLAY_MS = 5_000;
const SWIPE_THRESHOLD_PX = 48;

const SLIDES: HomeFeatureSlide[] = [
  {
    image: "/images/home-carousel/bs-ckii-ngo-thi-ngoc-van-tu-van-dieu-tri-cho-nguoi-benh-1548.jpg",
    imageAlt: "Bác sĩ tư vấn và trao đổi hướng điều trị trực tiếp với người bệnh",
    icon: Stethoscope,
    title: "Tư vấn trực tiếp",
    description: "Mọi quyết định y khoa do bác sĩ phụ trách.",
  },
  {
    image: "/images/home-carousel/co-nen-hoc-nganh-bac-si-da-lieu.png",
    imageAlt: "Bác sĩ da liễu trong môi trường khám và tư vấn chuyên môn",
    icon: BrainCircuit,
    title: "AI hỗ trợ đánh giá da",
    description: "Phân tích hình ảnh da và cung cấp kết quả tham khảo trước khi khám.",
  },
  {
    image: "/images/home-carousel/kham-bac-si.jpg",
    imageAlt: "Bệnh nhân đến khám và trao đổi trực tiếp với bác sĩ",
    icon: CalendarCheck,
    title: "Đặt lịch dễ dàng",
    description: "Chọn bác sĩ, ngày và khung giờ phù hợp chỉ trong vài bước.",
  },
  {
    image: "/images/home-carousel/lieu-trinh-cham-soc-da-mat.jpeg",
    imageAlt: "Quy trình chăm sóc da mặt được thực hiện tại cơ sở chuyên môn",
    icon: MessagesSquare,
    title: "Hỗ trợ khi bạn cần",
    description: "Trợ lý AI hỗ trợ trước và chuyển tiếp đến lễ tân khi cần thiết.",
  },
];

export default function HomeFeatureCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const carouselRef = useRef<HTMLElement>(null);
  const pointerStartX = useRef<number | null>(null);

  const goTo = useCallback((index: number) => {
    setActiveIndex((index + SLIDES.length) % SLIDES.length);
  }, []);

  const showPrevious = useCallback(() => {
    setActiveIndex((current) => (current - 1 + SLIDES.length) % SLIDES.length);
  }, []);

  const showNext = useCallback(() => {
    setActiveIndex((current) => (current + 1) % SLIDES.length);
  }, []);

  // A single timeout is restarted after every interaction, avoiding overlapping autoplay ticks.
  useEffect(() => {
    if (paused) return;
    const timeout = window.setTimeout(showNext, AUTO_PLAY_MS);
    return () => window.clearTimeout(timeout);
  }, [activeIndex, paused, showNext]);

  // Preload only the next frame; the first image remains the sole eager hero request.
  useEffect(() => {
    const nextImage = new Image();
    nextImage.src = SLIDES[(activeIndex + 1) % SLIDES.length].image;
  }, [activeIndex]);

  function handlePointerDown(event: ReactPointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse") return;
    pointerStartX.current = event.clientX;
    setPaused(true);
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLElement>) {
    const startX = pointerStartX.current;
    pointerStartX.current = null;
    setPaused(false);
    if (startX === null) return;
    const distance = event.clientX - startX;
    if (Math.abs(distance) < SWIPE_THRESHOLD_PX) return;
    if (distance > 0) showPrevious();
    else showNext();
  }

  // Desktop pointer position and keyboard focus must not silently disable
  // autoplay; pausing is limited to an active touch swipe on the carousel.
  return (
    <section
      ref={carouselRef}
      className="clinic-home-feature-carousel"
      role="region"
      aria-label="Điểm nổi bật của Derm Clinic"
      aria-roledescription="carousel"
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => {
        pointerStartX.current = null;
        setPaused(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") showPrevious();
        if (event.key === "ArrowRight") showNext();
      }}
    >
      <div className="clinic-home-feature-stage">
        {SLIDES.map((slide, index) => {
          const Icon = slide.icon;
          const active = index === activeIndex;
          return (
            <article
              key={slide.title}
              className={`clinic-home-feature-slide ${active ? "is-active" : ""}`}
              aria-hidden={!active}
            >
              <div className="clinic-home-feature-image">
                <img
                  src={slide.image}
                  alt={slide.imageAlt}
                  width="1536"
                  height="1024"
                  loading={index === 0 ? "eager" : "lazy"}
                  fetchPriority={index === 0 ? "high" : "auto"}
                />
              </div>
              <div className="clinic-home-feature-copy">
                <Icon aria-hidden="true" />
                <div>
                  <h2>{slide.title}</h2>
                  <p>{slide.description}</p>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <div className="clinic-home-feature-controls">
        <div className="clinic-home-feature-dots" role="group" aria-label="Chọn nội dung nổi bật">
          {SLIDES.map((slide, index) => (
            <button
              key={slide.title}
              type="button"
              className={index === activeIndex ? "is-active" : ""}
              aria-label={`Xem ${slide.title}`}
              aria-current={index === activeIndex ? "true" : undefined}
              onClick={() => goTo(index)}
            />
          ))}
        </div>
        <div className="clinic-home-feature-arrows">
          <button type="button" aria-label="Slide trước" onClick={showPrevious}><ChevronLeft aria-hidden="true" /></button>
          <button type="button" aria-label="Slide tiếp theo" onClick={showNext}><ChevronRight aria-hidden="true" /></button>
        </div>
      </div>
    </section>
  );
}
