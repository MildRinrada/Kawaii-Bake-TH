"use client";

/**
 * A self-contained emoji picker: category tabs, keyword search
 * (Thai + English), and a recently-used row persisted in localStorage.
 *
 * Built for composer-style forms - the categories admin picks a glyph,
 * never types one by hand. No external data: the set below is curated
 * for KawaiiBake (bakery-heavy on purpose).
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/cn";

type EmojiEntry = {
  emoji: string;
  /** Space-separated search keywords, Thai and English mixed. */
  keywords: string;
};

type EmojiCategory = {
  key: string;
  label: string;
  entries: EmojiEntry[];
};

const CATEGORIES: EmojiCategory[] = [
  {
    key: "bakery",
    label: "เบเกอรี่",
    entries: [
      { emoji: "🧁", keywords: "cupcake คัพเค้ก เค้ก ขนม" },
      { emoji: "🍰", keywords: "cake เค้ก ชิ้นเค้ก ขนม" },
      { emoji: "🎂", keywords: "birthday cake เค้กวันเกิด ฉลอง" },
      { emoji: "🍪", keywords: "cookie คุกกี้ ขนม" },
      { emoji: "🥐", keywords: "croissant ครัวซองต์ ขนมปัง" },
      { emoji: "🥖", keywords: "baguette บาแกตต์ ขนมปัง" },
      { emoji: "🍞", keywords: "bread ขนมปัง" },
      { emoji: "🥯", keywords: "bagel เบเกิล ขนมปัง" },
      { emoji: "🥨", keywords: "pretzel เพรตเซล" },
      { emoji: "🧇", keywords: "waffle วาฟเฟิล" },
      { emoji: "🥞", keywords: "pancake แพนเค้ก" },
      { emoji: "🍩", keywords: "donut โดนัท ขนม" },
      { emoji: "🥧", keywords: "pie พาย ขนม" },
      { emoji: "🍮", keywords: "custard คัสตาร์ด พุดดิ้ง" },
      { emoji: "🍫", keywords: "chocolate ช็อกโกแลต" },
      { emoji: "🍬", keywords: "candy ลูกอม" },
      { emoji: "🍭", keywords: "lollipop อมยิ้ม" },
      { emoji: "🍯", keywords: "honey น้ำผึ้ง" },
      { emoji: "🍓", keywords: "strawberry สตรอว์เบอร์รี ผลไม้" },
      { emoji: "🍒", keywords: "cherry เชอร์รี ผลไม้" },
      { emoji: "🫐", keywords: "blueberry บลูเบอร์รี ผลไม้" },
      { emoji: "🍋", keywords: "lemon เลมอน มะนาว" },
      { emoji: "🥝", keywords: "kiwi กีวี" },
      { emoji: "🍦", keywords: "ice cream ไอศกรีม ซอฟต์ครีม" },
      { emoji: "🍨", keywords: "sundae ไอศกรีม" },
      { emoji: "🥛", keywords: "milk นม" },
      { emoji: "☕", keywords: "coffee กาแฟ" },
      { emoji: "🍵", keywords: "tea ชา ชาเขียว" },
      { emoji: "🧈", keywords: "butter เนย" },
      { emoji: "🥚", keywords: "egg ไข่" },
      { emoji: "🌾", keywords: "wheat แป้ง ข้าวสาลี" },
      { emoji: "👩‍🍳", keywords: "chef เชฟ ทำอาหาร อบขนม" },
      { emoji: "🧑‍🍳", keywords: "chef เชฟ ทำอาหาร อบขนม" },
    ],
  },
  {
    key: "celebrate",
    label: "ฉลอง",
    entries: [
      { emoji: "🎉", keywords: "party ฉลอง ยินดี ปาร์ตี้" },
      { emoji: "🎊", keywords: "confetti ฉลอง ยินดี" },
      { emoji: "🥳", keywords: "party face ฉลอง ปาร์ตี้" },
      { emoji: "🎈", keywords: "balloon ลูกโป่ง" },
      { emoji: "🎁", keywords: "gift ของขวัญ" },
      { emoji: "🏆", keywords: "trophy ถ้วยรางวัล ชนะ ความสำเร็จ" },
      { emoji: "🎖️", keywords: "medal เหรียญ รางวัล" },
      { emoji: "🥇", keywords: "gold medal เหรียญทอง ที่หนึ่ง" },
      { emoji: "🎓", keywords: "graduation เรียนจบ รับปริญญา" },
      { emoji: "📜", keywords: "certificate ใบประกาศ ประกาศนียบัตร" },
      { emoji: "🌟", keywords: "star ดาว เด่น" },
      { emoji: "✨", keywords: "sparkle ประกาย พิเศษ ใหม่" },
      { emoji: "🔥", keywords: "fire ไฟ ฮิต ไวรัล มาแรง" },
      { emoji: "🚩", keywords: "flag ธง หมุดหมาย milestone" },
      { emoji: "🎪", keywords: "event งาน กิจกรรม" },
      { emoji: "🎨", keywords: "art ศิลปะ ตกแต่ง" },
    ],
  },
  {
    key: "hearts",
    label: "หัวใจ",
    entries: [
      { emoji: "💖", keywords: "heart หัวใจ ถูกใจ รัก" },
      { emoji: "❤️", keywords: "heart หัวใจ รัก" },
      { emoji: "🩷", keywords: "pink heart หัวใจชมพู" },
      { emoji: "💗", keywords: "growing heart หัวใจ" },
      { emoji: "💕", keywords: "hearts หัวใจ รัก" },
      { emoji: "💌", keywords: "love letter จดหมาย" },
      { emoji: "😊", keywords: "smile ยิ้ม" },
      { emoji: "😍", keywords: "heart eyes หลงรัก ถูกใจ" },
      { emoji: "🤩", keywords: "star struck ว้าว ตื่นเต้น" },
      { emoji: "😋", keywords: "yummy อร่อย" },
      { emoji: "🥰", keywords: "loved อบอุ่น รัก" },
      { emoji: "👍", keywords: "thumbs up เยี่ยม ถูกใจ" },
      { emoji: "👏", keywords: "clap ปรบมือ เก่ง" },
      { emoji: "🙌", keywords: "hooray ไชโย" },
    ],
  },
  {
    key: "messages",
    label: "ข้อความ",
    entries: [
      { emoji: "📢", keywords: "announcement ประกาศ โฆษณา" },
      { emoji: "📣", keywords: "megaphone ประกาศ โทรโข่ง" },
      { emoji: "📻", keywords: "radio วิทยุ ข่าว" },
      { emoji: "🔔", keywords: "bell กระดิ่ง แจ้งเตือน" },
      { emoji: "💬", keywords: "comment คอมเมนต์ แชท ข้อความ" },
      { emoji: "↩️", keywords: "reply ตอบกลับ" },
      { emoji: "📩", keywords: "inbox ข้อความ จดหมาย" },
      { emoji: "📌", keywords: "pin ปักหมุด" },
      { emoji: "🔖", keywords: "bookmark บุ๊กมาร์ก บันทึก" },
      { emoji: "❓", keywords: "question คำถาม ถามตอบ" },
      { emoji: "📝", keywords: "memo โน้ต แบบทดสอบ ควิซ" },
      { emoji: "📚", keywords: "books หนังสือ คอร์ส เรียน" },
      { emoji: "🆕", keywords: "new ใหม่" },
      { emoji: "⏰", keywords: "alarm นาฬิกา เตือน" },
      { emoji: "📅", keywords: "calendar ปฏิทิน นัดหมาย" },
      { emoji: "🛠️", keywords: "tools อัปเดต ปรับปรุง เครื่องมือ" },
      { emoji: "🚧", keywords: "maintenance ปิดปรับปรุง ก่อสร้าง" },
      { emoji: "🛡️", keywords: "shield ดูแล ปลอดภัย โล่" },
      { emoji: "🔄", keywords: "update รีเฟรช อัปเดต" },
    ],
  },
];

const RECENT_KEY = "kb-emoji-recent";
const RECENT_MAX = 16;

function readRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function EmojiPicker({
  value,
  onPick,
  label = "เลือกอีโมจิ",
}: {
  value: string;
  onPick: (emoji: string) => void;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0].key);
  const [recent, setRecent] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const cleanedQuery = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (!cleanedQuery) return null;
    return CATEGORIES.flatMap((group) =>
      group.entries.filter((entry) =>
        entry.keywords.toLowerCase().includes(cleanedQuery),
      ),
    );
  }, [cleanedQuery]);

  function pick(emoji: string) {
    const next = [emoji, ...readRecent().filter((item) => item !== emoji)].slice(
      0,
      RECENT_MAX,
    );
    try {
      window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      // Storage may be unavailable (private mode) - picking still works.
    }
    setRecent(next);
    onPick(emoji);
    setOpen(false);
  }

  const shown =
    results ??
    CATEGORIES.find((group) => group.key === category)?.entries ??
    [];

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={label}
        onClick={() => {
          // Refresh the recent row on open - reading storage in the
          // event handler keeps the effect subscription-only.
          if (!open) setRecent(readRecent());
          setOpen((state) => !state);
        }}
        className="flex h-11 min-w-11 items-center justify-center gap-2 rounded-md border border-edge bg-surface px-3 text-xl hover:border-edge-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      >
        <span aria-hidden>{value || "🙂"}</span>
        <span className="text-xs font-medium text-fg-muted">{label}</span>
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={label}
          className="absolute z-30 mt-1 w-72 rounded-md border border-edge bg-surface-raised p-2 shadow-overlay"
        >
          <input
            type="text"
            value={query}
            autoFocus
            placeholder="ค้นหาอีโมจิ เช่น เค้ก ประกาศ…"
            aria-label="ค้นหาอีโมจิ"
            onChange={(event) => setQuery(event.target.value)}
            className="mb-2 w-full rounded border border-edge bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent"
          />

          {!results && recent.length > 0 ? (
            <div className="mb-1">
              <p className="px-1 text-[11px] font-medium text-fg-subtle">
                ใช้ล่าสุด
              </p>
              <div className="flex flex-wrap">
                {recent.map((emoji) => (
                  <button
                    key={`recent-${emoji}`}
                    type="button"
                    onClick={() => pick(emoji)}
                    className="flex size-8 items-center justify-center rounded text-lg hover:bg-accent-subtle"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {!results ? (
            <div
              role="tablist"
              aria-label="หมวดอีโมจิ"
              className="mb-1 flex gap-1"
            >
              {CATEGORIES.map((group) => (
                <button
                  key={group.key}
                  type="button"
                  role="tab"
                  aria-selected={category === group.key}
                  onClick={() => setCategory(group.key)}
                  className={cn(
                    "rounded px-2 py-1 text-xs",
                    category === group.key
                      ? "bg-accent-subtle font-medium text-fg"
                      : "text-fg-muted hover:bg-surface-sunken",
                  )}
                >
                  {group.label}
                </button>
              ))}
            </div>
          ) : null}

          <div className="flex max-h-44 flex-wrap overflow-y-auto">
            {shown.map((entry) => (
              <button
                key={entry.emoji}
                type="button"
                title={entry.keywords.split(" ")[0]}
                onClick={() => pick(entry.emoji)}
                className="flex size-8 items-center justify-center rounded text-lg hover:bg-accent-subtle"
              >
                {entry.emoji}
              </button>
            ))}
            {shown.length === 0 ? (
              <p className="px-1 py-3 text-xs text-fg-muted">
                ไม่พบอีโมจิที่ตรงกับคำค้น
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
