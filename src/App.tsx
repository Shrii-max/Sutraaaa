import { FormEvent, useEffect, useMemo, useState } from "react";
import sutraAssistantLogo from "./assets/sutra-ai-assistant.png";
import sutraLogo from "./assets/sutra-logo.png";

type IconName =
  | "archive"
  | "bell"
  | "book"
  | "briefcase"
  | "calendar"
  | "chevron"
  | "clock"
  | "close"
  | "dashboard"
  | "document"
  | "download"
  | "folder"
  | "gavel"
  | "help"
  | "home"
  | "message"
  | "maximize"
  | "minus"
  | "more"
  | "plus"
  | "research"
  | "search"
  | "settings"
  | "sparkles"
  | "timeline"
  | "upload"
  | "users";

function Icon({
  name,
  size = 18,
  strokeWidth = 1.8,
}: {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}) {
  const paths: Record<IconName, React.ReactNode> = {
    archive: (
      <>
        <path d="M21 8v13H3V8" />
        <path d="M1 3h22v5H1zM10 12h4" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" />
      </>
    ),
    book: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      </>
    ),
    briefcase: (
      <>
        <rect x="3" y="7" width="18" height="13" rx="2" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M16 3v4M8 3v4M3 10h18" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    close: <path d="M18 6 6 18M6 6l12 12" />,
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    document: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12M7 10l5 5 5-5" />
        <path d="M5 21h14" />
      </>
    ),
    folder: <path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />,
    gavel: (
      <>
        <path d="m14 13-7.5 7.5M8 8l8 8M13 3l8 8M6 10l7-7 8 8-7 7Z" />
        <path d="M2 22h9" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.7 9a2.4 2.4 0 1 1 3.5 2.1c-.8.4-1.2.9-1.2 1.9M12 17h.01" />
      </>
    ),
    home: (
      <>
        <path d="m3 11 9-8 9 8" />
        <path d="M5 10v11h14V10M9 21v-7h6v7" />
      </>
    ),
    message: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z" />,
    maximize: (
      <>
        <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
      </>
    ),
    minus: <path d="M5 12h14" />,
    more: (
      <>
        <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    research: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5M8 8h5M8 11h4" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    sparkles: (
      <>
        <path d="m12 3-1 3.1A4 4 0 0 1 8.1 9L5 10l3.1 1A4 4 0 0 1 11 13.9l1 3.1 1-3.1a4 4 0 0 1 2.9-2.9l3.1-1-3.1-1A4 4 0 0 1 13 6.1Z" />
        <path d="m19 17-.4 1.2a2 2 0 0 1-1.2 1.2l-1.4.6 1.4.6a2 2 0 0 1 1.2 1.2L19 23l.4-1.2a2 2 0 0 1 1.2-1.2l1.4-.6-1.4-.6a2 2 0 0 1-1.2-1.2Z" />
      </>
    ),
    timeline: (
      <>
        <path d="M6 4v16" />
        <circle cx="6" cy="7" r="2" />
        <circle cx="6" cy="17" r="2" />
        <path d="M10 7h10M10 17h7" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V4M7 9l5-5 5 5" />
        <path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4" />
      </>
    ),
    users: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
      </>
    ),
  };

  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={strokeWidth}
    >
      {paths[name]}
    </svg>
  );
}

const navigation: { label: string; icon: IconName }[] = [
  { label: "Dashboard", icon: "dashboard" },
  { label: "My Cases", icon: "briefcase" },
  { label: "AI Assistant", icon: "sparkles" },
];

const initialCases = [
  {
    id: "CT-2024-084",
    title: "ABC Traders vs XYZ Enterprises",
    type: "Commercial Dispute",
    updated: "Today, 9:42 AM",
    status: "Active",
  },
  {
    id: "CT-2024-071",
    title: "Sharma vs State",
    type: "Criminal Appeal",
    updated: "Yesterday, 4:18 PM",
    status: "Under Review",
  },
  {
    id: "CT-2024-059",
    title: "Mehta Enterprises Payment Dispute",
    type: "Contract Law",
    updated: "12 Jun 2025",
    status: "Active",
  },
  {
    id: "CT-2024-033",
    title: "Kapoor Family Property Matter",
    type: "Property Law",
    updated: "08 Jun 2025",
    status: "Completed",
  },
];

type PageName =
  | "Dashboard"
  | "My Cases"
  | "Case Workspace"
  | "Documents"
  | "Document Preview"
  | "Case Timeline"
  | "Case Evidence"
  | "AI Case Summary & Assistant"
  | "Legal Research"
  | "Similar Cases"
  | "Language Converter"
  | "AI Assistant"
  | "Settings"
  | "Help & Support"
  | "Sign In";

const currentUser = {
  name: "Aditi Khanna",
  email: "aditi.khanna@sutra.demo",
  role: "Senior Counsel",
  initials: "AK",
};

type ManagedCase = {
  id: string;
  title: string;
  type: string;
  opposingParty: string;
  documents: number;
  updated: string;
  status: "Active" | "Under Review" | "Completed";
};

const initialManagedCases: ManagedCase[] = [
  {
    id: "ST-2026-001",
    title: "Sharma Enterprises vs. Verma Traders",
    type: "Civil Payment Dispute",
    opposingParty: "Verma Traders",
    documents: 9,
    updated: "Today",
    status: "Active",
  },
  {
    id: "CT-2026-001",
    title: "ABC Traders vs XYZ Enterprises",
    type: "Commercial Dispute",
    opposingParty: "XYZ Enterprises",
    documents: 12,
    updated: "Today",
    status: "Active",
  },
  {
    id: "CT-2026-002",
    title: "Sharma vs State",
    type: "Criminal Appeal",
    opposingParty: "State Government",
    documents: 8,
    updated: "Yesterday",
    status: "Under Review",
  },
  {
    id: "CT-2026-003",
    title: "Mehta Enterprises Payment Dispute",
    type: "Contract Law",
    opposingParty: "Mehta Enterprises",
    documents: 16,
    updated: "12 Nov 2026",
    status: "Active",
  },
  {
    id: "CT-2026-004",
    title: "Kapoor Family Property Matter",
    type: "Property Law",
    opposingParty: "Kapoor Family",
    documents: 6,
    updated: "10 Nov 2026",
    status: "Completed",
  },
];

const kpis: {
  label: string;
  value: string;
  note: string;
  icon: IconName;
  tone: string;
}[] = [
  {
    label: "Active Cases",
    value: "24",
    note: "3 updated this week",
    icon: "briefcase",
    tone: "blue",
  },
  {
    label: "Documents Uploaded",
    value: "1,248",
    note: "32 added this month",
    icon: "document",
    tone: "violet",
  },
  {
    label: "Pending Reviews",
    value: "18",
    note: "6 marked high priority",
    icon: "clock",
    tone: "amber",
  },
  {
    label: "Important Events",
    value: "386",
    note: "Awaiting lawyer review",
    icon: "timeline",
    tone: "green",
  },
];

const hearings = [
  {
    day: "18",
    month: "JUN",
    title: "ABC Traders vs XYZ Enterprises",
    court: "Delhi High Court · Courtroom 12",
    time: "10:30 AM",
    status: "Confirmed",
  },
  {
    day: "21",
    month: "JUN",
    title: "Sharma vs State",
    court: "Supreme Court of India · Court 5",
    time: "2:15 PM",
    status: "Scheduled",
  },
];

const activities: { text: string; subject: string; time: string; icon: IconName; tone: string }[] =
  [
    {
      text: "New document uploaded",
      subject: "Witness Statement — R. Khanna.pdf",
      time: "12 min ago",
      icon: "document",
      tone: "blue",
    },
    {
      text: "Timeline generated",
      subject: "ABC Traders vs XYZ Enterprises",
      time: "1 hr ago",
      icon: "timeline",
      tone: "violet",
    },
    {
      text: "Evidence reviewed",
      subject: "Email correspondence — Batch 04",
      time: "3 hrs ago",
      icon: "search",
      tone: "green",
    },
    {
      text: "Case summary updated",
      subject: "Sharma vs State",
      time: "Yesterday",
      icon: "document",
      tone: "amber",
    },
  ];

function Badge({ status }: { status: string }) {
  const className =
    status === "Active" || status === "Confirmed"
      ? "badge badge-green"
      : status === "Under Review" || status === "Scheduled"
        ? "badge badge-amber"
        : "badge badge-neutral";
  return <span className={className}>{status}</span>;
}

function Sidebar({
  active,
  onNavigate,
  onProfile,
  onLogout,
}: {
  active: PageName;
  onNavigate: (page: PageName) => void;
  onProfile: () => void;
  onLogout: () => void;
}) {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  return (
    <aside className="sidebar">
      <div className="brand">
        <img className="brand-logo" src={sutraLogo} alt="Sutra" />
      </div>

      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Primary navigation" className="sidebar-nav">
        {navigation.map((item) => (
          <button
            className={`nav-item ${
              active === item.label ||
              (active === "Case Workspace" && item.label === "My Cases") ||
              (active === "Documents" && item.label === "My Cases") ||
              (active === "Case Timeline" && item.label === "My Cases") ||
              (active === "Case Evidence" && item.label === "My Cases") ||
              (active === "AI Case Summary & Assistant" && item.label === "My Cases") ||
              (active === "Legal Research" && item.label === "My Cases") ||
              (active === "Similar Cases" && item.label === "My Cases") ||
              (active === "Language Converter" && item.label === "My Cases") ||
              (active === "Document Preview" && item.label === "My Cases")
                ? "active"
                : ""
            }`}
            key={item.label}
            onClick={() => {
              if (
                item.label === "Dashboard" ||
                item.label === "My Cases" ||
                item.label === "AI Assistant"
              ) {
                onNavigate(item.label);
              }
            }}
            title={
              item.label === "Dashboard" ||
              item.label === "My Cases" ||
              item.label === "AI Assistant"
                ? undefined
                : "Preview only — page not created yet"
            }
            type="button"
          >
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
            {item.label === "AI Assistant" && <span className="nav-beta">BETA</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button
          className={`nav-item ${active === "Help & Support" ? "active" : ""}`}
          onClick={() => onNavigate("Help & Support")}
          type="button"
        >
          <Icon name="help" size={18} />
          <span>Help & Support</span>
        </button>
        <div className="sidebar-profile-wrap">
          {profileMenuOpen && (
            <div className="sidebar-profile-menu">
              <div className="sidebar-profile-menu-identity">
                <strong>Adv. {currentUser.name}</strong>
                <span>{currentUser.email}</span>
              </div>
              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  onProfile();
                }}
                type="button"
              >
                <Icon name="users" size={15} />
                My Profile
              </button>
              <button
                onClick={() => {
                  setProfileMenuOpen(false);
                  onNavigate("Settings");
                }}
                type="button"
              >
                <Icon name="settings" size={15} />
                Settings
              </button>
              <button
                className="logout-option"
                onClick={() => {
                  setProfileMenuOpen(false);
                  onLogout();
                }}
                type="button"
              >
                <Icon name="close" size={15} />
                Log Out
              </button>
            </div>
          )}
          <button
            aria-expanded={profileMenuOpen}
            className={`profile-card ${profileMenuOpen ? "active" : ""} ${
              active === "Settings" ? "settings-active" : ""
            }`}
            onClick={() => setProfileMenuOpen((current) => !current)}
            type="button"
          >
            <div className="avatar">{currentUser.initials}</div>
            <div className="profile-copy">
              <strong>Adv. {currentUser.name}</strong>
              <span>{currentUser.role}</span>
            </div>
            <Icon name="more" size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}

function NewCaseDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (title: string, type: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState("Commercial Dispute");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (title.trim()) onCreate(title.trim(), type);
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        aria-labelledby="new-case-heading"
        aria-modal="true"
        className="modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="modal-head">
          <div>
            <h2 id="new-case-heading">Create a new case</h2>
            <p>Add the core details. Documents and parties can be added next.</p>
          </div>
          <button aria-label="Close dialog" className="icon-button" onClick={onClose} type="button">
            <Icon name="close" size={19} />
          </button>
        </div>
        <form onSubmit={submit}>
          <label className="field-label" htmlFor="case-title">
            Case title
          </label>
          <input
            autoFocus
            className="field-input"
            id="case-title"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Patel Industries vs Rao & Co."
            required
            value={title}
          />
          <label className="field-label" htmlFor="case-type">
            Case type
          </label>
          <select
            className="field-input"
            id="case-type"
            onChange={(event) => setType(event.target.value)}
            value={type}
          >
            <option>Commercial Dispute</option>
            <option>Contract Law</option>
            <option>Criminal Appeal</option>
            <option>Property Law</option>
            <option>Civil Litigation</option>
          </select>
          <div className="modal-actions">
            <button className="secondary-button" onClick={onClose} type="button">
              Cancel
            </button>
            <button className="primary-button" type="submit">
              Create case
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const caseSummary = [
  { label: "Total Cases", value: "48", icon: "folder" as IconName, tone: "blue" },
  { label: "Active Cases", value: "24", icon: "briefcase" as IconName, tone: "green" },
  { label: "Under Review", value: "18", icon: "clock" as IconName, tone: "amber" },
  { label: "Completed Cases", value: "6", icon: "archive" as IconName, tone: "slate" },
];

function MyCasesPage({
  cases,
  onCreateCase,
  onOpenCase,
}: {
  cases: ManagedCase[];
  onCreateCase: () => void;
  onOpenCase: (caseItem: ManagedCase) => void;
}) {
  const [search, setSearch] = useState("");
  const [caseType, setCaseType] = useState("Case Type");
  const [status, setStatus] = useState("Status");
  const [date, setDate] = useState("Date");
  const [sort, setSort] = useState("Recently Updated");
  const [view, setView] = useState<"list" | "grid">("list");
  const [paginationPage, setPaginationPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const filteredCases = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const result = cases.filter((item) => {
      const matchesSearch =
        !normalized ||
        item.id.toLowerCase().includes(normalized) ||
        item.title.toLowerCase().includes(normalized);
      const matchesType = caseType === "Case Type" || item.type === caseType;
      const matchesStatus = status === "Status" || item.status === status;
      const matchesDate =
        date === "Date" ||
        (date === "Updated today" && item.updated === "Today") ||
        (date === "This week" && ["Today", "Yesterday"].includes(item.updated));
      return matchesSearch && matchesType && matchesStatus && matchesDate;
    });

    if (sort === "Case Name") return [...result].sort((a, b) => a.title.localeCompare(b.title));
    if (sort === "Case ID") return [...result].sort((a, b) => a.id.localeCompare(b.id));
    return result;
  }, [caseType, cases, date, search, sort, status]);

  const allSelected =
    filteredCases.length > 0 && filteredCases.every((item) => selected.includes(item.id));

  function toggleAll() {
    setSelected((current) =>
      allSelected
        ? current.filter((id) => !filteredCases.some((item) => item.id === id))
        : [...new Set([...current, ...filteredCases.map((item) => item.id)])],
    );
  }

  function toggleCase(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  function clearFilters() {
    setSearch("");
    setCaseType("Case Type");
    setStatus("Status");
    setDate("Date");
    setSort("Recently Updated");
  }

  function openWorkspace(caseItem: ManagedCase) {
    setOpenMenu(null);
    onOpenCase(caseItem);
  }

  return (
    <div className="dashboard-content my-cases-content">
      <section className="cases-page-intro">
        <div>
          <div className="eyebrow">CASE MANAGEMENT</div>
          <h2>My Cases</h2>
          <p>Manage, organize and track all your legal matters.</p>
        </div>
        <button className="primary-button create-case-button" onClick={onCreateCase} type="button">
          <Icon name="plus" size={18} strokeWidth={2.2} />
          Create New Case
        </button>
      </section>

      <section aria-label="Case summary" className="case-summary-grid">
        {caseSummary.map((item) => (
          <article className="case-summary-card" key={item.label}>
            <div className={`kpi-icon ${item.tone}`}>
              <Icon name={item.icon} size={19} />
            </div>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="card managed-cases-card">
        <div className="cases-toolbar">
          <div className="cases-toolbar-row cases-toolbar-primary">
            <label className="case-search">
              <Icon name="search" size={17} />
              <input
                aria-label="Search cases"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by case name or case ID..."
                value={search}
              />
            </label>
            <label className="filter-control">
              <span className="sr-only">Case type</span>
              <select onChange={(event) => setCaseType(event.target.value)} value={caseType}>
                <option>Case Type</option>
                <option>Commercial Dispute</option>
                <option>Criminal Appeal</option>
                <option>Contract Law</option>
                <option>Property Law</option>
              </select>
              <Icon name="chevron" size={13} />
            </label>
            <label className="filter-control">
              <span className="sr-only">Status</span>
              <select onChange={(event) => setStatus(event.target.value)} value={status}>
                <option>Status</option>
                <option>Active</option>
                <option>Under Review</option>
                <option>Completed</option>
              </select>
              <Icon name="chevron" size={13} />
            </label>
            <label className="filter-control date-filter">
              <Icon name="calendar" size={15} />
              <span className="sr-only">Date filter</span>
              <select onChange={(event) => setDate(event.target.value)} value={date}>
                <option>Date</option>
                <option>Updated today</option>
                <option>This week</option>
              </select>
              <Icon name="chevron" size={13} />
            </label>
          </div>
          <div className="cases-toolbar-row cases-toolbar-secondary">
            <label className="filter-control sort-filter">
              <span className="sort-prefix">Sort by:</span>
              <span className="sr-only">Sort cases</span>
              <select onChange={(event) => setSort(event.target.value)} value={sort}>
                <option>Recently Updated</option>
                <option>Case Name</option>
                <option>Case ID</option>
              </select>
              <Icon name="chevron" size={13} />
            </label>
            <div className="view-toggle" aria-label="Case view">
              <button
                aria-label="List view"
                className={view === "list" ? "active" : ""}
                onClick={() => setView("list")}
                type="button"
              >
                <Icon name="timeline" size={16} />
              </button>
              <button
                aria-label="Grid view"
                className={view === "grid" ? "active" : ""}
                onClick={() => setView("grid")}
                type="button"
              >
                <Icon name="dashboard" size={15} />
              </button>
            </div>
            <button className="clear-filters" onClick={clearFilters} type="button">
              <Icon name="close" size={13} />
              Clear filters
            </button>
          </div>
        </div>

        <div className="filter-meta-row">
          <div>
            <strong>{filteredCases.length} cases</strong>
            <span>Fictional matters for demonstration</span>
          </div>
        </div>

        {view === "list" ? (
          <div className="managed-table-wrap">
            <table className="managed-cases-table">
              <colgroup>
                <col className="select-column" />
                <col className="managed-id-column" />
                <col className="managed-name-column" />
                <col className="managed-type-column" />
                <col className="managed-docs-column" />
                <col className="managed-updated-column" />
                <col className="managed-status-column" />
                <col className="managed-action-column" />
              </colgroup>
              <thead>
                <tr>
                  <th>
                    <input
                      aria-label="Select all cases"
                      checked={allSelected}
                      onChange={toggleAll}
                      type="checkbox"
                    />
                  </th>
                  <th>Case ID</th>
                  <th>Case Name</th>
                  <th>Case Type</th>
                  <th>Documents</th>
                  <th>Last Updated</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredCases.map((caseItem) => (
                  <tr
                    className={selected.includes(caseItem.id) ? "selected" : ""}
                    key={caseItem.id}
                  >
                    <td>
                      <input
                        aria-label={`Select ${caseItem.title}`}
                        checked={selected.includes(caseItem.id)}
                        onChange={() => toggleCase(caseItem.id)}
                        type="checkbox"
                      />
                    </td>
                    <td>
                      <span className="case-id">{caseItem.id}</span>
                    </td>
                    <td>
                      <button
                        className="managed-case-link"
                        onClick={() => openWorkspace(caseItem)}
                        type="button"
                      >
                        {caseItem.title}
                      </button>
                      <span className="opposing-party">
                        Opposing party: {caseItem.opposingParty}
                      </span>
                    </td>
                    <td>{caseItem.type}</td>
                    <td>
                      <span className="document-count">
                        <Icon name="document" size={13} />
                        {caseItem.documents}
                      </span>
                    </td>
                    <td>{caseItem.updated}</td>
                    <td>
                      <Badge status={caseItem.status} />
                    </td>
                    <td className="managed-action-cell">
                      <button
                        aria-label={`Actions for ${caseItem.title}`}
                        className="more-button"
                        onClick={() =>
                          setOpenMenu((current) => (current === caseItem.id ? null : caseItem.id))
                        }
                        type="button"
                      >
                        <Icon name="more" size={18} />
                      </button>
                      {openMenu === caseItem.id && (
                        <div className="case-action-menu">
                          <button onClick={() => openWorkspace(caseItem)} type="button">
                            Open workspace
                          </button>
                          <button type="button">View documents</button>
                          <button type="button">Archive case</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredCases.length === 0 && (
              <div className="managed-empty-state">
                <Icon name="folder" size={24} />
                <strong>No cases found</strong>
                <span>Try changing or clearing the current filters.</span>
              </div>
            )}
          </div>
        ) : (
          <div className="managed-case-grid">
            {filteredCases.map((caseItem) => (
              <article className="managed-case-card" key={caseItem.id}>
                <div className="managed-case-card-top">
                  <span className="case-id">{caseItem.id}</span>
                  <Badge status={caseItem.status} />
                </div>
                <button onClick={() => openWorkspace(caseItem)} type="button">
                  {caseItem.title}
                </button>
                <p>
                  {caseItem.type} · {caseItem.opposingParty}
                </p>
                <div>
                  <span>
                    <Icon name="document" size={14} />
                    {caseItem.documents} documents
                  </span>
                  <span>{caseItem.updated}</span>
                </div>
              </article>
            ))}
          </div>
        )}

        <footer className="cases-pagination">
          <span>
            Showing {(paginationPage - 1) * 4 + 1}–{Math.min(paginationPage * 4, 48)} of 48 cases
          </span>
          <div>
            <button
              disabled={paginationPage === 1}
              onClick={() => setPaginationPage((current) => Math.max(1, current - 1))}
              type="button"
            >
              <Icon name="chevron" size={14} />
            </button>
            <button
              className={paginationPage === 1 ? "active" : ""}
              onClick={() => setPaginationPage(1)}
              type="button"
            >
              1
            </button>
            <button
              className={paginationPage === 2 ? "active" : ""}
              onClick={() => setPaginationPage(2)}
              type="button"
            >
              2
            </button>
            <button
              className={paginationPage === 3 ? "active" : ""}
              onClick={() => setPaginationPage(3)}
              type="button"
            >
              3
            </button>
            <span>…</span>
            <button
              className={paginationPage === 12 ? "active" : ""}
              onClick={() => setPaginationPage(12)}
              type="button"
            >
              12
            </button>
            <button
              className="next-page"
              disabled={paginationPage === 12}
              onClick={() => setPaginationPage((current) => Math.min(12, current + 1))}
              type="button"
            >
              <Icon name="chevron" size={14} />
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}

const workspaceDocuments = [
  { name: "Agreement.pdf", type: "Agreement", status: "Processed" },
  { name: "Invoice_001.pdf", type: "Invoice", status: "Processed" },
  { name: "Legal_Notice.pdf", type: "Legal Notice", status: "Under Review" },
  { name: "Payment_Receipt.pdf", type: "Receipt", status: "Processed" },
];

const caseActivities = [
  { label: "Case created", detail: "Matter added by Adv. Aditi Khanna", time: "10 Nov" },
  { label: "Agreement uploaded", detail: "Agreement.pdf added to case documents", time: "11 Nov" },
  { label: "Invoice documents processed", detail: "Text extraction completed", time: "12 Nov" },
  { label: "Timeline generated", detail: "8 events suggested for lawyer review", time: "12 Nov" },
  { label: "Evidence reviewed", detail: "Payment record marked for follow-up", time: "Today" },
];

const insightGroups = [
  {
    title: "Important Facts",
    tone: "fact",
    icon: "document" as IconName,
    items: [
      {
        text: "Agreement signed on 12 January 2025.",
        source: "Agreement.pdf — Page 2",
        status: "Verified",
      },
      {
        text: "Payment of ₹5,00,000 recorded.",
        source: "Payment_Receipt.pdf — Page 1",
        status: "Needs Review",
      },
      {
        text: "Legal notice issued on 15 March 2025.",
        source: "Legal_Notice.pdf — Page 1",
        status: "Verified",
      },
    ],
  },
  {
    title: "Important Events",
    tone: "event",
    icon: "timeline" as IconName,
    items: [
      {
        text: "Agreement execution",
        source: "Agreement.pdf — Page 2",
        status: "Verified",
      },
      {
        text: "Payment due date",
        source: "Agreement.pdf — Page 4",
        status: "Needs Review",
      },
      {
        text: "Payment default",
        source: "Legal_Notice.pdf — Page 2",
        status: "Needs Review",
      },
      {
        text: "Legal notice issued",
        source: "Legal_Notice.pdf — Page 1",
        status: "Verified",
      },
    ],
  },
  {
    title: "Potential Contradictions",
    tone: "conflict",
    icon: "help" as IconName,
    items: [
      {
        text: "Invoice amount differs from the amount mentioned in the payment record.",
        source: "Invoice_001.pdf — Page 1 · Payment_Receipt.pdf — Page 1",
        status: "Conflicting Information",
      },
    ],
  },
  {
    title: "Missing Information",
    tone: "missing",
    icon: "search" as IconName,
    items: [
      {
        text: "Payment confirmation for the final invoice requires review.",
        source: "Invoice_001.pdf — Page 2",
        status: "Needs Review",
      },
    ],
  },
];

function CaseWorkspace({
  caseItem,
  onBack,
  onOpenDocuments,
  onOpenTimeline,
  onOpenEvidence,
  onOpenLanguage,
  onOpenAssistant,
  onOpenResearch,
  onOpenSimilar,
}: {
  caseItem: ManagedCase;
  onBack: () => void;
  onOpenDocuments: () => void;
  onOpenTimeline: () => void;
  onOpenEvidence: () => void;
  onOpenLanguage: () => void;
  onOpenAssistant: () => void;
  onOpenResearch: () => void;
  onOpenSimilar: () => void;
}) {
  const [showMore, setShowMore] = useState(false);
  const [fileName, setFileName] = useState("Agreement_Scan.pdf");
  const [uploadProgress, setUploadProgress] = useState(68);
  const [reviewNotice, setReviewNotice] = useState(false);
  const titleParts = caseItem.title.split(/\s+vs\.?\s+/i);
  const plaintiff = titleParts[0] ?? "Plaintiff";
  const defendant = titleParts[1] ?? caseItem.opposingParty;
  const caseDocuments =
    caseItem.id === "ST-2026-001"
      ? [
          { name: "Payment_Agreement.pdf", type: "Agreement", status: "Processed" },
          { name: "Invoice_2026_014.pdf", type: "Invoice", status: "Under Review" },
          { name: "Demand_Notice.pdf", type: "Legal Notice", status: "Processed" },
          { name: "Delivery_Receipt.pdf", type: "Receipt", status: "Under Review" },
        ]
      : workspaceDocuments;

  function selectFiles(files: FileList | null) {
    if (!files?.length) return;
    setFileName(files[0].name);
    setUploadProgress(24);
  }

  return (
    <div className="workspace-content">
      <div className="workspace-breadcrumb">
        <button onClick={onBack} type="button">
          My Cases
        </button>
        <Icon name="chevron" size={13} />
        <span>{caseItem.title}</span>
      </div>

      <section className="case-workspace-header">
        <div className="workspace-title-block">
          <div className="workspace-title-line">
            <h2>{caseItem.title}</h2>
            <Badge status="Active" />
          </div>
          <div className="workspace-case-meta">
            <span>{caseItem.id}</span>
            <i />
            <span>{caseItem.type}</span>
            <i />
            <span>Delhi High Court</span>
          </div>
          <p>Last updated today at 9:42 AM by Adv. Aditi Khanna</p>
        </div>
        <div className="workspace-header-actions">
          <button className="secondary-button" type="button">
            Edit Case
          </button>
          <div className="workspace-more-wrap">
            <button
              aria-label="More case options"
              className="icon-button"
              onClick={() => setShowMore((current) => !current)}
              type="button"
            >
              <Icon name="more" size={19} />
            </button>
            {showMore && (
              <div className="workspace-more-menu">
                <button type="button">Export case summary</button>
                <button type="button">Manage access</button>
                <button type="button">Archive case</button>
              </div>
            )}
          </div>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "Overview" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Documents") onOpenDocuments();
              if (tab === "Timeline") onOpenTimeline();
              if (tab === "Evidence") onOpenEvidence();
              if (tab === "Language Converter") onOpenLanguage();
              if (tab === "AI Summary & Assistant") onOpenAssistant();
              if (tab === "Legal Research") onOpenResearch();
              if (tab === "Similar Cases") onOpenSimilar();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="workspace-layout">
        <div className="workspace-left-column">
          <section className="card workspace-card case-information-card">
            <div className="workspace-card-heading">
              <div>
                <h3>Case Information</h3>
                <p>Core matter details and ownership.</p>
              </div>
              <Icon name="briefcase" size={18} />
            </div>
            <p className="case-description">
              {caseItem.type} concerning delayed invoice payments under a written supply agreement.
              Details shown are fictional demonstration data.
            </p>
            <dl className="case-details-grid">
              <div>
                <dt>Plaintiff</dt>
                <dd>{plaintiff}</dd>
              </div>
              <div>
                <dt>Defendant</dt>
                <dd>{defendant}</dd>
              </div>
              <div>
                <dt>Case type</dt>
                <dd>{caseItem.type}</dd>
              </div>
              <div>
                <dt>Court</dt>
                <dd>Delhi High Court</dd>
              </div>
              <div>
                <dt>Assigned lawyer</dt>
                <dd>Adv. Aditi Khanna</dd>
              </div>
              <div>
                <dt>Filing date</dt>
                <dd>10 November 2026</dd>
              </div>
              <div>
                <dt>Current status</dt>
                <dd>
                  <Badge status="Active" />
                </dd>
              </div>
            </dl>
          </section>

          <section className="card workspace-card recent-documents-card">
            <div className="workspace-card-heading">
              <div>
                <h3>Recent Documents</h3>
                <p>Files most recently added to this matter.</p>
              </div>
              <button
                className="secondary-button compact-button"
                onClick={() => document.getElementById("workspace-file-input")?.click()}
                type="button"
              >
                <Icon name="upload" size={15} />
                Upload Documents
              </button>
            </div>
            <div className="workspace-document-list">
              {caseDocuments.map((document) => (
                <div className="workspace-document-row" key={document.name}>
                  <div className="document-file-icon">
                    <Icon name="document" size={16} />
                  </div>
                  <div>
                    <strong>{document.name}</strong>
                    <span>{document.type}</span>
                  </div>
                  <span
                    className={`processing-status ${
                      document.status === "Processed" ? "processed" : "review"
                    }`}
                  >
                    {document.status}
                  </span>
                  <button aria-label={`Options for ${document.name}`} type="button">
                    <Icon name="more" size={17} />
                  </button>
                </div>
              ))}
            </div>
            <button className="workspace-card-link" type="button">
              View All Documents <Icon name="chevron" size={14} />
            </button>
          </section>

          <section className="card workspace-card activity-feed-card">
            <div className="workspace-card-heading">
              <div>
                <h3>Case Activity</h3>
                <p>Recent updates across this case.</p>
              </div>
            </div>
            <div className="case-activity-list">
              {caseActivities.map((activity, index) => (
                <div className="case-activity-row" key={activity.label}>
                  <div className="activity-marker">
                    <span />
                    {index < caseActivities.length - 1 && <i />}
                  </div>
                  <div>
                    <strong>{activity.label}</strong>
                    <span>{activity.detail}</span>
                  </div>
                  <time>{activity.time}</time>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="workspace-right-column">
          <section className="card workspace-card ai-insights-card">
            <div className="ai-card-header">
              <div className="ai-heading-icon">
                <Icon name="sparkles" size={18} />
              </div>
              <div>
                <h3>AI Case Insights</h3>
                <p>Extracted suggestions requiring lawyer review.</p>
              </div>
              <span className="ai-label">AI ASSISTED</span>
            </div>
            <div className="ai-disclaimer">
              <Icon name="help" size={14} />
              <span>These are AI-assisted extractions, not verified legal conclusions.</span>
            </div>
            <div className="insight-groups">
              {insightGroups.map((group) => (
                <div className={`insight-group ${group.tone}`} key={group.title}>
                  <div className="insight-group-title">
                    <Icon name={group.icon} size={14} />
                    <strong>{group.title}</strong>
                    <span>{group.items.length}</span>
                  </div>
                  {group.items.map((item) => (
                    <article className="insight-item" key={item.text}>
                      <p>{item.text}</p>
                      <div>
                        <span className="insight-source">{item.source}</span>
                        <span
                          className={`review-status ${
                            item.status === "Verified"
                              ? "verified"
                              : item.status === "Conflicting Information"
                                ? "conflicting"
                                : "needs-review"
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              ))}
            </div>
            {reviewNotice && (
              <div className="review-notice">
                Review queue opened with 5 items requiring attention.
              </div>
            )}
            <button
              className="primary-button review-insights-button"
              onClick={() => setReviewNotice(true)}
              type="button"
            >
              Review All Insights
            </button>
          </section>

          <section
            className="card workspace-card upload-concept-card"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              selectFiles(event.dataTransfer.files);
            }}
          >
            <div className="upload-drop-area">
              <div className="upload-icon">
                <Icon name="upload" size={18} />
              </div>
              <div>
                <strong>Upload case documents</strong>
                <span>Drag and drop files here, or</span>
              </div>
              <label className="browse-files-button">
                Browse Files
                <input
                  accept=".pdf,.docx,image/*"
                  id="workspace-file-input"
                  multiple
                  onChange={(event) => selectFiles(event.target.files)}
                  type="file"
                />
              </label>
            </div>
            <div className="upload-support">
              <span>PDF, DOCX and images</span>
              <span>Multilingual documents supported</span>
            </div>
            <div className="upload-progress-row">
              <div>
                <span>{fileName}</span>
                <strong>{uploadProgress}%</strong>
              </div>
              <div className="upload-progress-track">
                <span style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

type ManagedDocument = {
  name: string;
  caseName: string;
  type: string;
  language: "English" | "Hindi";
  size: string;
  date: string;
  status: "Processed" | "Processing" | "Needs Review";
};

const managedDocuments: ManagedDocument[] = [
  {
    name: "Payment_Agreement.pdf",
    caseName: "Sharma Enterprises vs. Verma Traders",
    type: "Agreement",
    language: "English",
    size: "2.1 MB",
    date: "18 Jan 2026",
    status: "Processed",
  },
  {
    name: "Invoice_2026_014.pdf",
    caseName: "Sharma Enterprises vs. Verma Traders",
    type: "Invoice",
    language: "English",
    size: "1.4 MB",
    date: "22 Feb 2026",
    status: "Needs Review",
  },
  {
    name: "Demand_Notice.pdf",
    caseName: "Sharma Enterprises vs. Verma Traders",
    type: "Legal Notice",
    language: "Hindi",
    size: "2.8 MB",
    date: "12 Mar 2026",
    status: "Processed",
  },
  {
    name: "Agreement.pdf",
    caseName: "ABC Traders vs XYZ Enterprises",
    type: "Agreement",
    language: "English",
    size: "2.4 MB",
    date: "14 Nov 2026",
    status: "Processed",
  },
  {
    name: "Invoice_001.pdf",
    caseName: "ABC Traders vs XYZ Enterprises",
    type: "Invoice",
    language: "English",
    size: "1.2 MB",
    date: "13 Nov 2026",
    status: "Processed",
  },
  {
    name: "Legal_Notice.pdf",
    caseName: "Sharma vs State",
    type: "Legal Notice",
    language: "Hindi",
    size: "3.1 MB",
    date: "12 Nov 2026",
    status: "Needs Review",
  },
  {
    name: "Court_Order.pdf",
    caseName: "Kapoor Family Property Matter",
    type: "Court Order",
    language: "English",
    size: "1.8 MB",
    date: "11 Nov 2026",
    status: "Processing",
  },
];

const documentSummary = [
  { label: "Total Documents", value: "128", icon: "document" as IconName, tone: "blue" },
  { label: "Processed", value: "96", icon: "archive" as IconName, tone: "green" },
  { label: "Processing", value: "12", icon: "clock" as IconName, tone: "violet" },
  { label: "Needs Review", value: "20", icon: "help" as IconName, tone: "amber" },
];

function DocumentStatusBadge({ status }: { status: ManagedDocument["status"] }) {
  const tone =
    status === "Processed" ? "processed" : status === "Processing" ? "processing" : "review";
  return (
    <span className={`document-status-badge ${tone}`}>
      <i />
      {status}
    </span>
  );
}

function UploadDocumentsModal({ onClose }: { onClose: () => void }) {
  const [fileName, setFileName] = useState("Legal_Notice_Hindi.pdf");
  const [fileSize, setFileSize] = useState("3.1 MB");
  const [progress, setProgress] = useState(72);

  function chooseFile(files: FileList | null) {
    if (!files?.length) return;
    setFileName(files[0].name);
    setFileSize(`${(files[0].size / 1024 / 1024).toFixed(1)} MB`);
    setProgress(28);
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        aria-labelledby="upload-documents-title"
        aria-modal="true"
        className="modal documents-upload-modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="modal-head">
          <div>
            <h2 id="upload-documents-title">Upload Documents</h2>
            <p>Add Hindi or English files to your document workspace.</p>
          </div>
          <button aria-label="Close upload" className="icon-button" onClick={onClose} type="button">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div
          className="documents-modal-dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            chooseFile(event.dataTransfer.files);
          }}
        >
          <div className="documents-upload-icon">
            <Icon name="upload" size={22} />
          </div>
          <strong>Drag and drop your documents here</strong>
          <span>PDF, DOCX, PNG and JPG · Maximum 25 MB per file</span>
          <label className="primary-button upload-browse-label">
            Browse Files
            <input
              accept=".pdf,.docx,.png,.jpg,.jpeg"
              multiple
              onChange={(event) => chooseFile(event.target.files)}
              type="file"
            />
          </label>
          <small>Hindi and English documents supported</small>
        </div>
        <div className="modal-upload-progress">
          <div className="modal-upload-file">
            <div className="document-file-icon">
              <Icon name="document" size={16} />
            </div>
            <div>
              <strong>{fileName}</strong>
              <span>{fileSize} · Uploading</span>
            </div>
            <b>{progress}%</b>
          </div>
          <div className="upload-progress-track">
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>
        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="primary-button" onClick={onClose} type="button">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function DocumentsPage({
  onOpenDocument,
  onUpload,
  caseContext,
}: {
  onOpenDocument: (document: ManagedDocument) => void;
  onUpload: () => void;
  caseContext?: string;
}) {
  const [search, setSearch] = useState("");
  const [caseFilter, setCaseFilter] = useState(caseContext ?? "Case");
  const [typeFilter, setTypeFilter] = useState("Document Type");
  const [language, setLanguage] = useState("Language");
  const [status, setStatus] = useState("Processing Status");
  const [sort, setSort] = useState("Recently Uploaded");
  const [view, setView] = useState<"list" | "grid">("list");
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const visibleDocuments = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const result = managedDocuments.filter(
      (document) =>
        (!normalized || document.name.toLowerCase().includes(normalized)) &&
        (caseFilter === "Case" || document.caseName === caseFilter) &&
        (typeFilter === "Document Type" || document.type === typeFilter) &&
        (language === "Language" || document.language === language) &&
        (status === "Processing Status" || document.status === status),
    );
    return sort === "Document Name"
      ? [...result].sort((a, b) => a.name.localeCompare(b.name))
      : result;
  }, [caseFilter, language, search, sort, status, typeFilter]);

  return (
    <div className="dashboard-content documents-content">
      <section className="documents-intro">
        <div>
          <div className="eyebrow">DOCUMENT MANAGEMENT</div>
          <h2>Documents</h2>
          <p>Upload, organize and review your legal documents.</p>
        </div>
        <div className="demo-note">
          <span />
          Fictional demonstration data
        </div>
      </section>

      <section aria-label="Document overview" className="document-summary-grid">
        {documentSummary.map((item) => (
          <article className="document-summary-card" key={item.label}>
            <div className={`kpi-icon ${item.tone}`}>
              <Icon name={item.icon} size={19} />
            </div>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="card documents-management-card">
        <div className="documents-toolbar">
          <label className="case-search document-name-search">
            <Icon name="search" size={17} />
            <input
              aria-label="Search by document name"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by document name..."
              value={search}
            />
          </label>
          <label className="filter-control">
            <select
              aria-label="Filter by case"
              onChange={(event) => setCaseFilter(event.target.value)}
              value={caseFilter}
            >
              <option>Case</option>
              <option>ABC Traders vs XYZ Enterprises</option>
              <option>Sharma vs State</option>
              <option>Kapoor Family Property Matter</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <select
              aria-label="Filter by document type"
              onChange={(event) => setTypeFilter(event.target.value)}
              value={typeFilter}
            >
              <option>Document Type</option>
              <option>Agreement</option>
              <option>Invoice</option>
              <option>Legal Notice</option>
              <option>Court Order</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <select
              aria-label="Filter by language"
              onChange={(event) => setLanguage(event.target.value)}
              value={language}
            >
              <option>Language</option>
              <option>English</option>
              <option>Hindi</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <select
              aria-label="Filter by processing status"
              onChange={(event) => setStatus(event.target.value)}
              value={status}
            >
              <option>Processing Status</option>
              <option>Processed</option>
              <option>Processing</option>
              <option>Needs Review</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
        </div>
        <div className="documents-toolbar-secondary">
          <div>
            <strong>{visibleDocuments.length} documents</strong>
            <span>Hindi and English files</span>
          </div>
          <label className="filter-control documents-sort">
            <span className="sort-prefix">Sort by:</span>
            <select onChange={(event) => setSort(event.target.value)} value={sort}>
              <option>Recently Uploaded</option>
              <option>Document Name</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <div className="view-toggle">
            <button
              aria-label="List view"
              className={view === "list" ? "active" : ""}
              onClick={() => setView("list")}
              type="button"
            >
              <Icon name="timeline" size={16} />
            </button>
            <button
              aria-label="Grid view"
              className={view === "grid" ? "active" : ""}
              onClick={() => setView("grid")}
              type="button"
            >
              <Icon name="dashboard" size={15} />
            </button>
          </div>
        </div>

        {view === "list" ? (
          <div className="documents-table-wrap">
            <table className="documents-table">
              <colgroup>
                <col className="doc-name-column" />
                <col className="doc-case-column" />
                <col className="doc-type-column" />
                <col className="doc-language-column" />
                <col className="doc-size-column" />
                <col className="doc-date-column" />
                <col className="doc-status-column" />
                <col className="doc-action-column" />
              </colgroup>
              <thead>
                <tr>
                  <th>Document Name</th>
                  <th>Associated Case</th>
                  <th>Document Type</th>
                  <th>Language</th>
                  <th>File Size</th>
                  <th>Uploaded Date</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleDocuments.map((document) => (
                  <tr key={document.name} onClick={() => onOpenDocument(document)}>
                    <td>
                      <div className="document-name-cell">
                        <div className="document-file-icon">
                          <Icon name="document" size={15} />
                        </div>
                        <button onClick={() => onOpenDocument(document)} type="button">
                          {document.name}
                        </button>
                      </div>
                    </td>
                    <td>
                      <span className="associated-case">{document.caseName}</span>
                    </td>
                    <td>{document.type}</td>
                    <td>
                      <span className={`language-badge ${document.language.toLowerCase()}`}>
                        {document.language}
                      </span>
                    </td>
                    <td>{document.size}</td>
                    <td>{document.date}</td>
                    <td>
                      <DocumentStatusBadge status={document.status} />
                    </td>
                    <td
                      className="document-action-cell"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        className="more-button"
                        onClick={() =>
                          setOpenMenu((current) =>
                            current === document.name ? null : document.name,
                          )
                        }
                        type="button"
                      >
                        <Icon name="more" size={18} />
                      </button>
                      {openMenu === document.name && (
                        <div className="case-action-menu document-action-menu">
                          <button onClick={() => onOpenDocument(document)} type="button">
                            Open preview
                          </button>
                          <button type="button">Download</button>
                          <button type="button">Move to case</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="document-card-grid">
            {visibleDocuments.map((document) => (
              <article className="document-grid-card" key={document.name}>
                <div>
                  <div className="document-file-icon">
                    <Icon name="document" size={17} />
                  </div>
                  <DocumentStatusBadge status={document.status} />
                </div>
                <button onClick={() => onOpenDocument(document)} type="button">
                  {document.name}
                </button>
                <p>{document.caseName}</p>
                <footer>
                  <span>
                    {document.type} · {document.language}
                  </span>
                  <span>{document.size}</span>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card inline-upload-card">
        <div className="documents-upload-icon">
          <Icon name="upload" size={20} />
        </div>
        <div>
          <strong>Drag and drop your documents here</strong>
          <span>PDF, DOCX, PNG and JPG · Hindi and English supported</span>
        </div>
        <button className="secondary-button" onClick={onUpload} type="button">
          Browse Files
        </button>
        <div className="inline-progress">
          <div>
            <span>Legal_Notice_Hindi.pdf · 3.1 MB</span>
            <b>72%</b>
          </div>
          <div className="upload-progress-track">
            <span style={{ width: "72%" }} />
          </div>
        </div>
      </section>
    </div>
  );
}

function DocumentPreview({ document, onBack }: { document: ManagedDocument; onBack: () => void }) {
  const [tab, setTab] = useState<"original" | "translation">("original");
  const [reviewed, setReviewed] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [page, setPage] = useState(1);

  return (
    <div className="document-preview-content">
      <div className="workspace-breadcrumb">
        <button onClick={onBack} type="button">
          Documents
        </button>
        <Icon name="chevron" size={13} />
        <span>{document.name}</span>
      </div>
      <section className="document-preview-header">
        <div className="document-file-icon">
          <Icon name="document" size={18} />
        </div>
        <div>
          <h2>{document.name}</h2>
          <p>
            {document.caseName} · {document.size} · {document.language}
          </p>
        </div>
        <DocumentStatusBadge status={reviewed ? "Processed" : "Needs Review"} />
        <button className="secondary-button" type="button">
          <Icon name="download" size={15} />
          Download
        </button>
      </section>

      <div className="document-preview-layout">
        <section className="card original-document-panel">
          <header className="preview-panel-toolbar">
            <div>
              <strong>Original Document</strong>
              <span>Hindi · PDF</span>
            </div>
            <div className="pdf-controls">
              <button onClick={() => setPage(Math.max(1, page - 1))} type="button">
                <Icon name="chevron" size={14} />
              </button>
              <span>Page {page} of 3</span>
              <button onClick={() => setPage(Math.min(3, page + 1))} type="button">
                <Icon name="chevron" size={14} />
              </button>
              <i />
              <button onClick={() => setZoom(Math.max(75, zoom - 25))} type="button">
                −
              </button>
              <span>{zoom}%</span>
              <button onClick={() => setZoom(Math.min(150, zoom + 25))} type="button">
                +
              </button>
              <button type="button">
                <Icon name="download" size={14} />
              </button>
            </div>
          </header>
          <div className="pdf-canvas">
            <article className="pdf-page" style={{ transform: `scale(${zoom / 100})` }}>
              <div className="pdf-seal">न्यायालय</div>
              <h3>विधिक सूचना</h3>
              <p className="pdf-reference">दिनांक: 15 मार्च 2025</p>
              <p>
                सेवा में,
                <br />
                <strong>श्री शर्मा</strong>
                <br />
                नई दिल्ली
              </p>
              <p>विषय: अनुबंध के अंतर्गत बकाया भुगतान के संबंध में विधिक सूचना।</p>
              <p>
                महोदय, आपको सूचित किया जाता है कि दिनांक 12 जनवरी 2025 को निष्पादित अनुबंध के अनुसार देय राशि
                का भुगतान अभी तक प्राप्त नहीं हुआ है।
              </p>
              <p className="pdf-highlight">
                अतः आपको इस सूचना की प्राप्ति से पंद्रह दिनों के भीतर ₹5,00,000 की राशि का भुगतान करने के लिए
                कहा जाता है।
              </p>
              <p>अन्यथा उपलब्ध कानूनी उपाय अपनाए जाएंगे।</p>
              <div className="pdf-signature">
                अधिकृत अधिवक्ता
                <br />
                नई दिल्ली
              </div>
            </article>
          </div>
        </section>

        <section className="card extracted-text-panel">
          <header className="extracted-panel-heading">
            <div>
              <h3>Extracted Text</h3>
              <p>OCR output · Page {page}</p>
            </div>
            <span className="ocr-confidence">OCR 91%</span>
          </header>
          <div className="extracted-tabs">
            <button
              className={tab === "original" ? "active" : ""}
              onClick={() => setTab("original")}
              type="button"
            >
              Original Text
            </button>
            <button
              className={tab === "translation" ? "active" : ""}
              onClick={() => setTab("translation")}
              type="button"
            >
              English Translation
            </button>
          </div>
          <div className="extraction-warning">
            <Icon name="help" size={14} />
            <span>Extracted text and translations require lawyer verification.</span>
            {!reviewed && <span className="review-status needs-review">Needs Review</span>}
          </div>
          <article className={`extracted-copy ${tab}`}>
            <div className="page-reference">Source: Legal_Notice.pdf — Page {page}</div>
            {tab === "original" ? (
              <>
                <h4>विधिक सूचना</h4>
                <p>दिनांक: 15 मार्च 2025</p>
                <p>विषय: अनुबंध के अंतर्गत बकाया भुगतान के संबंध में विधिक सूचना।</p>
                <p>
                  आपको सूचित किया जाता है कि दिनांक 12 जनवरी 2025 को निष्पादित अनुबंध के अनुसार देय राशि का
                  भुगतान अभी तक प्राप्त नहीं हुआ है।
                </p>
                <p>
                  अतः आपको इस सूचना की प्राप्ति से पंद्रह दिनों के भीतर{" "}
                  <mark>₹5,00,000 की राशि [अस्पष्ट शब्द]</mark> का भुगतान करने के लिए कहा जाता है।
                </p>
                <p>अन्यथा उपलब्ध कानूनी उपाय अपनाए जाएंगे।</p>
              </>
            ) : (
              <>
                <h4>Legal Notice</h4>
                <p>Date: 15 March 2025</p>
                <p>Subject: Legal notice regarding outstanding payment under the agreement.</p>
                <p>
                  You are informed that payment due under the agreement executed on 12 January 2025
                  has not yet been received.
                </p>
                <p>
                  You are therefore requested to pay <mark>₹5,00,000 [uncertain OCR text]</mark>{" "}
                  within fifteen days of receiving this notice.
                </p>
                <p>Otherwise, available legal remedies may be pursued.</p>
              </>
            )}
            <div className="ocr-legend">
              <i />
              Amber text indicates uncertain OCR requiring review.
            </div>
          </article>
          <footer className="extracted-panel-footer">
            <span>{reviewed ? "Reviewed by lawyer" : "Not yet lawyer-verified"}</span>
            <button
              className={reviewed ? "secondary-button reviewed-button" : "primary-button"}
              onClick={() => setReviewed(true)}
              type="button"
            >
              {reviewed ? "Reviewed" : "Mark as Reviewed"}
            </button>
          </footer>
        </section>
      </div>
    </div>
  );
}

type TimelineEvent = {
  id: number;
  date: string;
  isoDate: string;
  title: string;
  description: string;
  fullDescription: string;
  type: string;
  people: string[];
  source: string;
  status: "Verified" | "Needs Review" | "Conflicting Information";
  amount?: string;
  passage: string;
};

const initialTimelineEvents: TimelineEvent[] = [
  {
    id: 1,
    date: "12 January 2025",
    isoDate: "2025-01-12",
    title: "Agreement Signed",
    description: "Agreement executed between ABC Traders and XYZ Enterprises.",
    fullDescription:
      "The commercial supply agreement was executed by authorized representatives of ABC Traders and XYZ Enterprises, establishing payment terms and delivery obligations.",
    type: "Agreement",
    people: ["ABC Traders", "XYZ Enterprises"],
    source: "Agreement.pdf — Page 2",
    status: "Verified",
    passage:
      "This Agreement is executed on 12 January 2025 between ABC Traders and XYZ Enterprises under the terms set out herein.",
  },
  {
    id: 2,
    date: "28 February 2025",
    isoDate: "2025-02-28",
    title: "Payment Due",
    description: "Payment deadline reached according to the agreement.",
    fullDescription:
      "The payment deadline specified in the agreement was reached. The extracted amount and due date require confirmation against the signed agreement.",
    type: "Payment",
    people: ["ABC Traders", "XYZ Enterprises"],
    source: "Agreement.pdf — Page 4",
    status: "Needs Review",
    amount: "₹5,00,000",
    passage: "The purchaser shall remit the amount of ₹5,00,000 on or before 28 February 2025.",
  },
  {
    id: 3,
    date: "10 March 2025",
    isoDate: "2025-03-10",
    title: "Payment Default",
    description: "Payment recorded as overdue.",
    fullDescription:
      "Invoice records indicate that the agreed payment remained outstanding after the due date. This event is AI-extracted and has not yet been lawyer-verified.",
    type: "Payment",
    people: ["XYZ Enterprises"],
    source: "Invoice_001.pdf — Page 1",
    status: "Needs Review",
    passage: "Outstanding balance: ₹5,00,000. Status recorded as overdue as of 10 March 2025.",
  },
  {
    id: 4,
    date: "15 March 2025",
    isoDate: "2025-03-15",
    title: "Legal Notice Issued",
    description: "Legal notice issued to the opposing party.",
    fullDescription:
      "A legal notice concerning the outstanding payment was issued to XYZ Enterprises by counsel acting for ABC Traders.",
    type: "Legal Notice",
    people: ["ABC Traders", "XYZ Enterprises", "Adv. Aditi Khanna"],
    source: "Legal_Notice.pdf — Page 1",
    status: "Verified",
    passage:
      "You are hereby called upon to remit the outstanding payment within fifteen days from receipt of this notice.",
  },
  {
    id: 5,
    date: "20 March 2025",
    isoDate: "2025-03-20",
    title: "Payment Dispute Raised",
    description: "Dispute regarding the outstanding payment amount.",
    fullDescription:
      "The payment receipt records an amount that differs from the outstanding amount stated in the invoice. Both source records require lawyer comparison.",
    type: "Dispute",
    people: ["ABC Traders", "XYZ Enterprises"],
    source: "Payment_Receipt.pdf — Page 1",
    status: "Conflicting Information",
    passage:
      "Payment received: ₹4,50,000 against the referenced invoice. Balance shown differs from the invoice record.",
  },
];

function TimelineStatusBadge({ status }: { status: TimelineEvent["status"] }) {
  const tone =
    status === "Verified" ? "verified" : status === "Needs Review" ? "needs-review" : "conflicting";
  return (
    <span className={`timeline-status ${tone}`}>
      <i />
      {status}
    </span>
  );
}

function CaseTimelinePage({
  caseItem,
  onViewSource,
}: {
  caseItem: ManagedCase;
  onViewSource: (event: TimelineEvent) => void;
}) {
  const [events, setEvents] = useState(() =>
    caseItem.id === "ST-2026-001"
      ? initialTimelineEvents.map((event) => ({
          ...event,
          date: event.date.replace("2025", "2026"),
          isoDate: event.isoDate.replace("2025", "2026"),
          description: event.description
            .replaceAll("ABC Traders", "Sharma Enterprises")
            .replaceAll("XYZ Enterprises", "Verma Traders"),
          fullDescription: event.fullDescription
            .replaceAll("ABC Traders", "Sharma Enterprises")
            .replaceAll("XYZ Enterprises", "Verma Traders"),
          people: event.people.map((person) =>
            person
              .replaceAll("ABC Traders", "Sharma Enterprises")
              .replaceAll("XYZ Enterprises", "Verma Traders"),
          ),
          source: event.source
            .replace("Agreement.pdf", "Payment_Agreement.pdf")
            .replace("Invoice_001.pdf", "Invoice_2026_014.pdf")
            .replace("Legal_Notice.pdf", "Demand_Notice.pdf")
            .replace("Payment_Receipt.pdf", "Delivery_Receipt.pdf"),
          passage: event.passage
            .replaceAll("2025", "2026")
            .replaceAll("ABC Traders", "Sharma Enterprises")
            .replaceAll("XYZ Enterprises", "Verma Traders"),
        }))
      : initialTimelineEvents,
  );
  const [selectedId, setSelectedId] = useState(1);
  const [expandedId, setExpandedId] = useState(1);
  const [search, setSearch] = useState("");
  const [eventType, setEventType] = useState("Event Type");
  const [documentFilter, setDocumentFilter] = useState("Document");
  const [verification, setVerification] = useState("Verification Status");
  const [dateRange, setDateRange] = useState("All dates");
  const [sort, setSort] = useState("Oldest First");
  const [exported, setExported] = useState(false);

  const visibleEvents = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const result = events.filter(
      (event) =>
        (!normalized || `${event.title} ${event.description}`.toLowerCase().includes(normalized)) &&
        (eventType === "Event Type" || event.type === eventType) &&
        (documentFilter === "Document" || event.source.startsWith(documentFilter)) &&
        (verification === "Verification Status" || event.status === verification) &&
        (dateRange === "All dates" ||
          (dateRange === "Jan – Feb 2025" && event.isoDate <= "2025-02-28") ||
          (dateRange === "March 2025" && event.isoDate >= "2025-03-01")),
    );
    return [...result].sort((a, b) =>
      sort === "Oldest First"
        ? a.isoDate.localeCompare(b.isoDate)
        : b.isoDate.localeCompare(a.isoDate),
    );
  }, [dateRange, documentFilter, eventType, events, search, sort, verification]);

  const selectedEvent = events.find((event) => event.id === selectedId) ?? events[0];
  const clearFilters = () => {
    setSearch("");
    setEventType("Event Type");
    setDocumentFilter("Document");
    setVerification("Verification Status");
    setDateRange("All dates");
    setSort("Oldest First");
  };
  const verifySelected = () =>
    setEvents((current) =>
      current.map((event) =>
        event.id === selectedEvent.id ? { ...event, status: "Verified" } : event,
      ),
    );

  return (
    <div className="dashboard-content timeline-content">
      <section className="timeline-page-header">
        <div>
          <div className="eyebrow">CASE CHRONOLOGY</div>
          <h2>Case Timeline</h2>
          <p>Explore important events and understand the chronological history of your case.</p>
        </div>
        <div className="timeline-header-actions">
          <label className="timeline-case-selector">
            <Icon name="briefcase" size={15} />
            <span>
              <small>SELECTED CASE</small>
              <strong>{caseItem.title}</strong>
              <i>{caseItem.id}</i>
            </span>
            <Icon name="chevron" size={13} />
          </label>
          <button className="icon-button" aria-label="Search timeline" type="button">
            <Icon name="search" size={17} />
          </button>
          <label className="timeline-range-selector">
            <Icon name="calendar" size={15} />
            <select value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
              <option>All dates</option>
              <option>Jan – Feb 2025</option>
              <option>March 2025</option>
            </select>
            <Icon name="chevron" size={12} />
          </label>
          <button
            className="secondary-button export-timeline-button"
            onClick={() => setExported(true)}
            type="button"
          >
            <Icon name="download" size={15} />
            Export Timeline
          </button>
        </div>
      </section>
      {exported && (
        <div className="timeline-export-notice" role="status">
          <Icon name="document" size={14} />
          Timeline export prepared for frontend preview.
          <button onClick={() => setExported(false)} type="button">
            <Icon name="close" size={13} />
          </button>
        </div>
      )}

      <section className="timeline-summary-grid">
        {[
          { label: "Total Events", value: "28", icon: "timeline" as IconName, tone: "blue" },
          { label: "Verified Events", value: "18", icon: "archive" as IconName, tone: "green" },
          { label: "Needs Review", value: "7", icon: "clock" as IconName, tone: "amber" },
          { label: "Conflicting Events", value: "3", icon: "help" as IconName, tone: "red" },
        ].map((item) => (
          <article className="timeline-summary-card" key={item.label}>
            <div className={`kpi-icon ${item.tone}`}>
              <Icon name={item.icon} size={18} />
            </div>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="card timeline-filter-card">
        <label className="case-search timeline-search">
          <Icon name="search" size={17} />
          <input
            aria-label="Search events"
            placeholder="Search events..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="filter-control">
          <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
            <option>Event Type</option>
            <option>Agreement</option>
            <option>Payment</option>
            <option>Legal Notice</option>
            <option>Dispute</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control">
          <select
            value={documentFilter}
            onChange={(event) => setDocumentFilter(event.target.value)}
          >
            <option>Document</option>
            {[...new Set(events.map((event) => event.source.split(" — ")[0]))].map((document) => (
              <option key={document}>{document}</option>
            ))}
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control">
          <select value={verification} onChange={(event) => setVerification(event.target.value)}>
            <option>Verification Status</option>
            <option>Verified</option>
            <option>Needs Review</option>
            <option>Conflicting Information</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control">
          <Icon name="calendar" size={14} />
          <select value={dateRange} onChange={(event) => setDateRange(event.target.value)}>
            <option>All dates</option>
            <option>Jan – Feb 2025</option>
            <option>March 2025</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control timeline-sort">
          <span className="sort-prefix">Sort:</span>
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option>Oldest First</option>
            <option>Newest First</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
      </section>

      <div className="timeline-workspace">
        <section className="timeline-list-section">
          <div className="timeline-list-heading">
            <div>
              <h3>Chronological Events</h3>
              <p>{visibleEvents.length} shown · AI-extracted events require lawyer review</p>
            </div>
            <button className="clear-filters" onClick={clearFilters} type="button">
              <Icon name="close" size={13} />
              Clear filters
            </button>
          </div>
          {visibleEvents.length ? (
            <div className="vertical-timeline">
              {visibleEvents.map((event) => {
                const expanded = event.id === expandedId;
                const tone =
                  event.status === "Verified"
                    ? "verified"
                    : event.status === "Needs Review"
                      ? "review"
                      : "conflict";
                return (
                  <article className={`timeline-event-row ${tone}`} key={event.id}>
                    <time>{event.date}</time>
                    <div className="timeline-marker">
                      <span>
                        <Icon
                          name={
                            event.type === "Legal Notice"
                              ? "gavel"
                              : event.type === "Payment"
                                ? "document"
                                : "timeline"
                          }
                          size={14}
                        />
                      </span>
                      <i />
                    </div>
                    <div
                      className={`card timeline-event-card ${selectedId === event.id ? "selected" : ""}`}
                      onClick={() => {
                        setSelectedId(event.id);
                        setExpandedId(event.id);
                      }}
                    >
                      <div className="timeline-event-main">
                        <div>
                          <span className="event-type-label">{event.type}</span>
                          <h4>{event.title}</h4>
                          <p>{event.description}</p>
                        </div>
                        <div className="timeline-card-actions">
                          <TimelineStatusBadge status={event.status} />
                          <button
                            aria-label={expanded ? "Collapse event" : "Expand event"}
                            onClick={(click) => {
                              click.stopPropagation();
                              setExpandedId(expanded ? 0 : event.id);
                              setSelectedId(event.id);
                            }}
                            type="button"
                          >
                            <Icon name="chevron" size={15} />
                          </button>
                        </div>
                      </div>
                      <div className="timeline-event-meta">
                        <span>
                          <Icon name="users" size={13} />
                          {event.people.join(", ")}
                        </span>
                        {event.amount && (
                          <span>
                            <strong>{event.amount}</strong>
                          </span>
                        )}
                        <button
                          onClick={(click) => {
                            click.stopPropagation();
                            onViewSource(event);
                          }}
                          type="button"
                        >
                          <Icon name="document" size={13} />
                          {event.source.replace(" — ", " → ")}
                        </button>
                      </div>
                      {expanded && (
                        <div className="timeline-event-expanded">
                          <p>{event.fullDescription}</p>
                          <span>
                            Extracted suggestion — compare with the original source before relying
                            on this event.
                          </span>
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="card empty-timeline-state">
              <div>
                <Icon name="timeline" size={24} />
              </div>
              <h3>No timeline events found</h3>
              <p>
                No events match the current filters. Clear filters to return to the full case
                chronology.
              </p>
              <button className="secondary-button" onClick={clearFilters} type="button">
                Clear Filters
              </button>
            </div>
          )}
        </section>

        <aside className="card event-details-panel">
          <header>
            <div>
              <span>EVENT DETAILS</span>
              <h3>{selectedEvent.title}</h3>
              <p>{selectedEvent.date}</p>
            </div>
            <TimelineStatusBadge status={selectedEvent.status} />
          </header>
          <div className="event-panel-body">
            <section>
              <h4>Description</h4>
              <p>{selectedEvent.fullDescription}</p>
            </section>
            <section>
              <h4>People Involved</h4>
              <div className="people-tags">
                {selectedEvent.people.map((person) => (
                  <span key={person}>
                    <Icon name="users" size={11} />
                    {person}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <h4>Related Document</h4>
              <button
                className="panel-source-link"
                onClick={() => onViewSource(selectedEvent)}
                type="button"
              >
                <div className="document-file-icon">
                  <Icon name="document" size={15} />
                </div>
                <span>
                  <strong>{selectedEvent.source.split(" — ")[0]}</strong>
                  <small>Source reference · {selectedEvent.source.split(" — ")[1]}</small>
                </span>
                <Icon name="chevron" size={14} />
              </button>
            </section>
            <section>
              <h4>Original Source Passage</h4>
              <blockquote>
                “{selectedEvent.passage}”<span>{selectedEvent.source.replace(" — ", " → ")}</span>
              </blockquote>
            </section>
            <div className="panel-verification-note">
              <Icon name="help" size={14} />
              <span>
                AI-extracted information is not automatically verified. Lawyer review is required.
              </span>
            </div>
          </div>
          <footer>
            <button className="secondary-button" type="button">
              Edit Event
            </button>
            <button
              className="secondary-button view-source-button"
              onClick={() => onViewSource(selectedEvent)}
              type="button"
            >
              View Source Document
            </button>
            <button className="primary-button" onClick={verifySelected} type="button">
              Mark as Verified
            </button>
          </footer>
        </aside>
      </div>
    </div>
  );
}

type EvidenceItem = {
  id: number;
  title: string;
  description: string;
  category: string;
  source: string;
  page: number;
  date: string;
  isoDate: string;
  status: "Verified" | "Needs Review" | "Conflicting Information";
  passage: string;
  timelineEvent: string;
};

const initialEvidence: EvidenceItem[] = [
  {
    id: 1,
    title: "Payment Agreement",
    description: "Agreement specifying payment obligations between the parties.",
    category: "Agreement",
    source: "Agreement.pdf",
    page: 2,
    date: "12 January 2025",
    isoDate: "2025-01-12",
    status: "Verified",
    passage:
      "The purchaser shall pay the agreed amount according to the payment schedule set out in this Agreement.",
    timelineEvent: "Agreement Signed",
  },
  {
    id: 2,
    title: "Outstanding Payment Invoice",
    description: "Invoice showing the amount claimed as outstanding.",
    category: "Financial Record",
    source: "Invoice_001.pdf",
    page: 1,
    date: "28 February 2025",
    isoDate: "2025-02-28",
    status: "Needs Review",
    passage: "Total amount due: ₹5,00,000. Payment status recorded as outstanding on the due date.",
    timelineEvent: "Payment Due",
  },
  {
    id: 3,
    title: "Legal Notice",
    description: "Notice issued regarding the payment dispute.",
    category: "Legal Notice",
    source: "Legal_Notice.pdf",
    page: 1,
    date: "15 March 2025",
    isoDate: "2025-03-15",
    status: "Verified",
    passage:
      "You are hereby called upon to remit the outstanding payment within fifteen days from receipt of this notice.",
    timelineEvent: "Legal Notice Issued",
  },
  {
    id: 4,
    title: "Payment Receipt",
    description: "Record relating to a payment made by the defendant.",
    category: "Financial Record",
    source: "Payment_Receipt.pdf",
    page: 1,
    date: "10 March 2025",
    isoDate: "2025-03-10",
    status: "Conflicting Information",
    passage:
      "Payment received: ₹4,50,000. The recorded amount differs from the invoice total referenced in the case file.",
    timelineEvent: "Payment Dispute Raised",
  },
];

const evidenceCategories = [
  { label: "All Evidence", value: "All Evidence" },
  { label: "Agreements", value: "Agreement" },
  { label: "Financial Records", value: "Financial Record" },
  { label: "Communications", value: "Communication" },
  { label: "Legal Notices", value: "Legal Notice" },
  { label: "Court Orders", value: "Court Order" },
  { label: "Other Documents", value: "Other Document" },
];

function CaseEvidencePage({
  caseItem,
  onViewSource,
  onOverview,
  onDocuments,
  onViewTimeline,
  onLanguage,
  onAssistant,
  onResearch,
  onSimilar,
}: {
  caseItem: ManagedCase;
  onViewSource: (evidence: EvidenceItem) => void;
  onOverview: () => void;
  onDocuments: () => void;
  onViewTimeline: () => void;
  onLanguage: () => void;
  onAssistant: () => void;
  onResearch: () => void;
  onSimilar: () => void;
}) {
  const [evidence, setEvidence] = useState(() =>
    caseItem.id === "ST-2026-001"
      ? initialEvidence.map((item) => ({
          ...item,
          date: item.date.replace("2025", "2026"),
          isoDate: item.isoDate.replace("2025", "2026"),
          source: item.source
            .replace("Agreement.pdf", "Payment_Agreement.pdf")
            .replace("Invoice_001.pdf", "Invoice_2026_014.pdf")
            .replace("Legal_Notice.pdf", "Demand_Notice.pdf")
            .replace("Payment_Receipt.pdf", "Delivery_Receipt.pdf"),
        }))
      : initialEvidence,
  );
  const [selectedId, setSelectedId] = useState(1);
  const [category, setCategory] = useState("All Evidence");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("Source Document");
  const [status, setStatus] = useState("Review Status");
  const [sort, setSort] = useState("Newest First");
  const [notesOpen, setNotesOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState("");
  const [savedNote, setSavedNote] = useState(
    "Compare the payment amount against the signed agreement before the next review.",
  );

  const visibleEvidence = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const result = evidence.filter(
      (item) =>
        (!normalized || `${item.title} ${item.description}`.toLowerCase().includes(normalized)) &&
        (category === "All Evidence" || item.category === category) &&
        (source === "Source Document" || item.source === source) &&
        (status === "Review Status" || item.status === status),
    );
    return [...result].sort((a, b) =>
      sort === "Newest First"
        ? b.isoDate.localeCompare(a.isoDate)
        : a.isoDate.localeCompare(b.isoDate),
    );
  }, [category, evidence, search, sort, source, status]);

  const selectedEvidence = evidence.find((item) => item.id === selectedId) ?? evidence[0];
  const clearFilters = () => {
    setCategory("All Evidence");
    setSearch("");
    setSource("Source Document");
    setStatus("Review Status");
    setSort("Newest First");
  };
  const verifySelected = () =>
    setEvidence((current) =>
      current.map((item) =>
        item.id === selectedEvidence.id ? { ...item, status: "Verified" } : item,
      ),
    );

  return (
    <div className="dashboard-content evidence-content">
      <section className="evidence-page-header">
        <div>
          <div className="eyebrow">CASE EVIDENCE</div>
          <h2>Case Evidence</h2>
          <p>Discover, organize and review important evidence from your case documents.</p>
          <div className="evidence-case-context">
            <Icon name="briefcase" size={13} />
            <strong>{caseItem.title}</strong>
            <span>{caseItem.id}</span>
          </div>
        </div>
        <div className="evidence-header-actions">
          <label className="timeline-case-selector">
            <Icon name="briefcase" size={15} />
            <span>
              <small>SELECTED CASE</small>
              <strong>{caseItem.title}</strong>
              <i>{caseItem.id}</i>
            </span>
            <Icon name="chevron" size={13} />
          </label>
          <label className="case-search evidence-header-search">
            <Icon name="search" size={16} />
            <input
              aria-label="Search evidence"
              placeholder="Search evidence..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <button className="secondary-button" onClick={() => setExportOpen(true)} type="button">
            <Icon name="download" size={15} />
            Export Evidence
          </button>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs case-evidence-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "Evidence" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Overview") onOverview();
              if (tab === "Documents") onDocuments();
              if (tab === "Timeline") onViewTimeline();
              if (tab === "Language Converter") onLanguage();
              if (tab === "AI Summary & Assistant") onAssistant();
              if (tab === "Legal Research") onResearch();
              if (tab === "Similar Cases") onSimilar();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <section className="evidence-summary-grid">
        {[
          { label: "Total Evidence", value: "42", icon: "search" as IconName, tone: "blue" },
          { label: "Documents", value: "18", icon: "document" as IconName, tone: "violet" },
          { label: "Needs Review", value: "12", icon: "clock" as IconName, tone: "amber" },
          { label: "Verified", value: "30", icon: "archive" as IconName, tone: "green" },
        ].map((item) => (
          <article className="evidence-summary-card" key={item.label}>
            <div className={`kpi-icon ${item.tone}`}>
              <Icon name={item.icon} size={18} />
            </div>
            <div>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="card evidence-controls">
        <nav className="evidence-category-tabs" aria-label="Evidence categories">
          {evidenceCategories.map((item) => (
            <button
              className={category === item.value ? "active" : ""}
              onClick={() => setCategory(item.value)}
              key={item.value}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="evidence-filter-row">
          <label className="case-search">
            <Icon name="search" size={16} />
            <input
              aria-label="Search by evidence name"
              placeholder="Search by evidence name..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="filter-control">
            <select value={source} onChange={(event) => setSource(event.target.value)}>
              <option>Source Document</option>
              {[...new Set(evidence.map((item) => item.source))].map((document) => (
                <option key={document}>{document}</option>
              ))}
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option>Review Status</option>
              <option>Verified</option>
              <option>Needs Review</option>
              <option>Conflicting Information</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <span className="sort-prefix">Sort:</span>
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option>Newest First</option>
              <option>Oldest First</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <button className="clear-filters" onClick={clearFilters} type="button">
            <Icon name="close" size={13} />
            Clear
          </button>
        </div>
      </section>

      <div className="evidence-workspace">
        <section className="evidence-list">
          <div className="evidence-list-heading">
            <div>
              <h3>Evidence Items</h3>
              <p>{visibleEvidence.length} shown · Fictional extracted information for review</p>
            </div>
            <span>Source-linked</span>
          </div>
          {visibleEvidence.length ? (
            visibleEvidence.map((item, index) => (
              <article
                className={`card evidence-item-card ${selectedId === item.id ? "selected" : ""}`}
                onClick={() => setSelectedId(item.id)}
                key={item.id}
              >
                <div
                  className={`evidence-category-icon category-${item.category.toLowerCase().replaceAll(" ", "-")}`}
                >
                  <Icon
                    name={
                      item.category === "Legal Notice"
                        ? "gavel"
                        : item.category === "Financial Record"
                          ? "document"
                          : "briefcase"
                    }
                    size={17}
                  />
                </div>
                <div className="evidence-card-copy">
                  <div>
                    <span>EVIDENCE {String(index + 1).padStart(2, "0")}</span>
                    <h4>{item.title}</h4>
                  </div>
                  <p>{item.description}</p>
                  <div className="evidence-card-meta">
                    <span>{item.category}</span>
                    <span>
                      <Icon name="calendar" size={12} />
                      {item.date}
                    </span>
                  </div>
                </div>
                <div className="evidence-card-source">
                  <TimelineStatusBadge status={item.status} />
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onViewSource(item);
                    }}
                    type="button"
                  >
                    <Icon name="document" size={13} />
                    {item.source} → Page {item.page}
                  </button>
                  <span>View Source</span>
                </div>
              </article>
            ))
          ) : (
            <div className="card empty-evidence-state">
              <div>
                <Icon name="search" size={24} />
              </div>
              <h3>No evidence found</h3>
              <p>No evidence matches the current search and filters.</p>
              <button className="secondary-button" onClick={clearFilters} type="button">
                Clear Filters
              </button>
            </div>
          )}
        </section>

        <aside className="card evidence-details-panel">
          <header>
            <div>
              <span>EVIDENCE DETAILS</span>
              <h3>{selectedEvidence.title}</h3>
              <p>Evidence ID · EV-{String(selectedEvidence.id).padStart(3, "0")}</p>
            </div>
            <TimelineStatusBadge status={selectedEvidence.status} />
          </header>
          <div className="evidence-panel-body">
            <section>
              <h4>Description</h4>
              <p>{selectedEvidence.description}</p>
            </section>
            <dl>
              <div>
                <dt>Associated case</dt>
                <dd>{caseItem.title}</dd>
              </div>
              <div>
                <dt>Category</dt>
                <dd>{selectedEvidence.category}</dd>
              </div>
              <div>
                <dt>Relevant date</dt>
                <dd>{selectedEvidence.date}</dd>
              </div>
              <div>
                <dt>Verification status</dt>
                <dd>
                  <TimelineStatusBadge status={selectedEvidence.status} />
                </dd>
              </div>
            </dl>
            <section>
              <h4>Source Document</h4>
              <button
                className="panel-source-link"
                onClick={() => onViewSource(selectedEvidence)}
                type="button"
              >
                <div className="document-file-icon">
                  <Icon name="document" size={15} />
                </div>
                <span>
                  <strong>{selectedEvidence.source}</strong>
                  <small>Original source · Page {selectedEvidence.page}</small>
                </span>
                <Icon name="chevron" size={14} />
              </button>
            </section>
            <section>
              <h4>Original Extracted Passage</h4>
              <blockquote>
                “{selectedEvidence.passage}”
                <span>
                  {selectedEvidence.source} → Page {selectedEvidence.page}
                </span>
              </blockquote>
            </section>
            <section>
              <h4>Related Timeline Event</h4>
              <button className="related-event-link" onClick={onViewTimeline} type="button">
                <div>
                  <Icon name="timeline" size={14} />
                </div>
                <span>
                  <strong>{selectedEvidence.timelineEvent}</strong>
                  <small>Open in Case Timeline</small>
                </span>
                <Icon name="chevron" size={14} />
              </button>
            </section>
            <section>
              <h4>Lawyer Notes</h4>
              <div className="lawyer-note">
                <p>{savedNote}</p>
                <span>Adv. Aditi Khanna · Today</span>
              </div>
            </section>
            <div className="panel-verification-note">
              <Icon name="help" size={14} />
              <span>
                Extracted evidence requires lawyer verification against its original source.
              </span>
            </div>
          </div>
          <footer>
            <button
              className="secondary-button"
              onClick={() => onViewSource(selectedEvidence)}
              type="button"
            >
              View Original Document
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                setNoteDraft(savedNote);
                setNotesOpen(true);
              }}
              type="button"
            >
              Add Notes
            </button>
            <button className="primary-button" onClick={verifySelected} type="button">
              Mark as Verified
            </button>
          </footer>
        </aside>
      </div>

      {notesOpen && (
        <div className="modal-backdrop" onMouseDown={() => setNotesOpen(false)}>
          <div
            className="modal evidence-notes-modal"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-head">
              <div>
                <h2>Add Lawyer Notes</h2>
                <p>{selectedEvidence.title} · Notes are part of this frontend prototype.</p>
              </div>
              <button className="icon-button" onClick={() => setNotesOpen(false)} type="button">
                <Icon name="close" size={18} />
              </button>
            </div>
            <label className="field-label" htmlFor="evidence-note">
              Review note
            </label>
            <textarea
              id="evidence-note"
              value={noteDraft}
              onChange={(event) => setNoteDraft(event.target.value)}
              placeholder="Add your observations or review instructions..."
            />
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={() => setNotesOpen(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  setSavedNote(noteDraft);
                  setNotesOpen(false);
                }}
                type="button"
              >
                Save Note
              </button>
            </div>
          </div>
        </div>
      )}

      {exportOpen && (
        <div className="modal-backdrop" onMouseDown={() => setExportOpen(false)}>
          <div
            className="modal evidence-export-modal"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-head">
              <div>
                <h2>Export Evidence</h2>
                <p>Choose a frontend export format.</p>
              </div>
              <button className="icon-button" onClick={() => setExportOpen(false)} type="button">
                <Icon name="close" size={18} />
              </button>
            </div>
            <div className="export-option-list">
              <button type="button">
                <Icon name="document" size={17} />
                <span>
                  <strong>Evidence summary</strong>
                  <small>PDF with source references and review states</small>
                </span>
              </button>
              <button type="button">
                <Icon name="timeline" size={17} />
                <span>
                  <strong>Chronological evidence</strong>
                  <small>Evidence ordered by relevant date</small>
                </span>
              </button>
              <button type="button">
                <Icon name="download" size={17} />
                <span>
                  <strong>Case data</strong>
                  <small>Structured CSV for the development prototype</small>
                </span>
              </button>
            </div>
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={() => setExportOpen(false)}
                type="button"
              >
                Cancel
              </button>
              <button className="primary-button" onClick={() => setExportOpen(false)} type="button">
                Export
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SummarySourceRow({
  document,
  page,
  status,
  onView,
}: {
  document?: string;
  page?: number;
  status: TimelineEvent["status"];
  onView?: () => void;
}) {
  return (
    <div className="summary-source-row">
      {document ? (
        <button onClick={onView} type="button">
          <Icon name="document" size={12} />
          {document} → Page {page}
        </button>
      ) : (
        <span className="no-source-indicator">
          <Icon name="help" size={12} />
          No source available
        </span>
      )}
      <TimelineStatusBadge status={status} />
    </div>
  );
}

function AICaseAssistantPage({
  caseItem,
  onOverview,
  onDocuments,
  onTimeline,
  onEvidence,
  onLanguage,
  onResearch,
  onSimilar,
  onViewDocument,
}: {
  caseItem: ManagedCase;
  onOverview: () => void;
  onDocuments: () => void;
  onTimeline: () => void;
  onEvidence: () => void;
  onLanguage: () => void;
  onResearch: () => void;
  onSimilar: () => void;
  onViewDocument: (name: string) => void;
}) {
  const [input, setInput] = useState("");
  const [chatStarted, setChatStarted] = useState(true);
  const [userQuestion, setUserQuestion] = useState(
    "Which documents mention the outstanding payment?",
  );

  const suggestedQuestions = [
    "What are the key events in this case?",
    "Which documents mention the outstanding payment?",
    "Are there conflicting dates across the documents?",
    "Which facts still need verification?",
  ];

  function sendMessage() {
    if (!input.trim()) return;
    setUserQuestion(input.trim());
    setInput("");
    setChatStarted(true);
  }

  return (
    <div className="workspace-content assistant-content">
      <div className="workspace-breadcrumb">
        <button onClick={onOverview} type="button">
          My Cases
        </button>
        <Icon name="chevron" size={13} />
        <span>{caseItem.title}</span>
        <Icon name="chevron" size={13} />
        <span>AI Case Summary & Assistant</span>
      </div>

      <section className="assistant-page-header">
        <div>
          <div className="eyebrow">CASE UNDERSTANDING</div>
          <h2>AI Case Summary & Assistant</h2>
          <p>Review document-grounded case information and ask questions within this matter.</p>
          <div className="assistant-case-meta">
            <strong>{caseItem.title}</strong>
            <span>{caseItem.id}</span>
            <span>{caseItem.type}</span>
            <Badge status="Active" />
          </div>
        </div>
        <div className="assistant-header-mark">
          <Icon name="sparkles" size={20} />
          <span>
            <strong>Case-grounded assistant</strong>
            <small>9 documents in context</small>
          </span>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs assistant-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "AI Summary & Assistant" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Overview") onOverview();
              if (tab === "Documents") onDocuments();
              if (tab === "Timeline") onTimeline();
              if (tab === "Evidence") onEvidence();
              if (tab === "Language Converter") onLanguage();
              if (tab === "Legal Research") onResearch();
              if (tab === "Similar Cases") onSimilar();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="assistant-disclaimer">
        <Icon name="help" size={14} />
        <span>
          AI-generated summaries and responses are for lawyer review. Verify information against
          original documents before relying on it.
        </span>
      </div>

      <div className="assistant-layout">
        <section className="assistant-summary-column">
          <div className="assistant-section-heading">
            <div>
              <h3>Case Summary</h3>
              <p>Structured from documents in the selected case.</p>
            </div>
            <span>Updated today, 10:24 AM</span>
          </div>

          <article className="card ai-summary-card overview-summary-card">
            <header>
              <div className="summary-card-icon blue">
                <Icon name="briefcase" size={16} />
              </div>
              <div>
                <h4>Case Overview</h4>
                <p>High-level matter context</p>
              </div>
            </header>
            <div className="summary-card-body">
              <p>
                Sharma Enterprises claims that Verma Traders failed to pay the remaining balance for
                goods supplied under a written agreement. Verma Traders disputes the amount
                reflected in the final invoice.
              </p>
            </div>
            <SummarySourceRow
              document="Payment_Agreement.pdf"
              page={1}
              status="Needs Review"
              onView={() => onViewDocument("Payment_Agreement.pdf")}
            />
          </article>

          <div className="summary-card-pair">
            <article className="card ai-summary-card">
              <header>
                <div className="summary-card-icon violet">
                  <Icon name="users" size={16} />
                </div>
                <div>
                  <h4>Parties Involved</h4>
                  <p>Named parties and roles</p>
                </div>
              </header>
              <div className="party-summary-list">
                <div>
                  <span>SE</span>
                  <p>
                    <strong>Sharma Enterprises</strong>
                    <small>Plaintiff · Supplier</small>
                  </p>
                </div>
                <div>
                  <span>VT</span>
                  <p>
                    <strong>Verma Traders</strong>
                    <small>Defendant · Purchaser</small>
                  </p>
                </div>
              </div>
              <SummarySourceRow
                document="Payment_Agreement.pdf"
                page={1}
                status="Verified"
                onView={() => onViewDocument("Payment_Agreement.pdf")}
              />
            </article>

            <article className="card ai-summary-card">
              <header>
                <div className="summary-card-icon green">
                  <Icon name="document" size={16} />
                </div>
                <div>
                  <h4>Important Amounts</h4>
                  <p>Financial figures mentioned</p>
                </div>
              </header>
              <div className="amount-summary-list">
                <div>
                  <span>Contract value</span>
                  <strong>₹8,75,000</strong>
                </div>
                <div>
                  <span>Claimed outstanding</span>
                  <strong>₹2,50,000</strong>
                </div>
              </div>
              <SummarySourceRow
                document="Invoice_2026_014.pdf"
                page={1}
                status="Needs Review"
                onView={() => onViewDocument("Invoice_2026_014.pdf")}
              />
            </article>
          </div>

          <article className="card ai-summary-card key-events-summary">
            <header>
              <div className="summary-card-icon amber">
                <Icon name="timeline" size={16} />
              </div>
              <div>
                <h4>Key Events</h4>
                <p>Chronology suggested from case documents</p>
              </div>
              <button onClick={onTimeline} type="button">
                Open Timeline <Icon name="chevron" size={13} />
              </button>
            </header>
            <div className="summary-event-list">
              {[
                {
                  date: "18 Jan 2026",
                  title: "Payment agreement executed",
                  doc: "Payment_Agreement.pdf",
                  page: 2,
                  status: "Verified" as const,
                },
                {
                  date: "22 Feb 2026",
                  title: "Final invoice issued",
                  doc: "Invoice_2026_014.pdf",
                  page: 1,
                  status: "Needs Review" as const,
                },
                {
                  date: "12 Mar 2026",
                  title: "Demand notice sent",
                  doc: "Demand_Notice.pdf",
                  page: 1,
                  status: "Verified" as const,
                },
              ].map((event) => (
                <button
                  className="summary-event-row"
                  onClick={onTimeline}
                  key={event.title}
                  type="button"
                >
                  <time>{event.date}</time>
                  <span>
                    <strong>{event.title}</strong>
                    <small>
                      {event.doc} → Page {event.page}
                    </small>
                  </span>
                  <TimelineStatusBadge status={event.status} />
                  <Icon name="chevron" size={13} />
                </button>
              ))}
            </div>
            <SummarySourceRow
              document="Demand_Notice.pdf"
              page={1}
              status="Verified"
              onView={() => onViewDocument("Demand_Notice.pdf")}
            />
          </article>

          <article className="card ai-summary-card pending-review-card">
            <header>
              <div className="summary-card-icon red">
                <Icon name="help" size={16} />
              </div>
              <div>
                <h4>Pending Review</h4>
                <p>Missing, uncertain or conflicting information</p>
              </div>
              <span className="review-count">3 items</span>
            </header>
            <div className="pending-review-list">
              <div>
                <i className="warning" />
                <span>
                  <strong>Payment due date differs across two records.</strong>
                  <small>Agreement states 20 Feb; invoice states 22 Feb 2026.</small>
                </span>
                <SummarySourceRow
                  document="Invoice_2026_014.pdf"
                  page={1}
                  status="Conflicting Information"
                  onView={() => onViewDocument("Invoice_2026_014.pdf")}
                />
              </div>
              <div>
                <i className="warning" />
                <span>
                  <strong>Delivery acknowledgment signature is unclear.</strong>
                  <small>Scan quality prevents confident identification.</small>
                </span>
                <SummarySourceRow
                  document="Delivery_Receipt.pdf"
                  page={1}
                  status="Needs Review"
                  onView={() => onViewDocument("Delivery_Receipt.pdf")}
                />
              </div>
              <div>
                <i />
                <span>
                  <strong>Verbal payment extension</strong>
                  <small>Mentioned in correspondence but no supporting file was found.</small>
                </span>
                <SummarySourceRow status="Needs Review" />
              </div>
            </div>
          </article>
        </section>

        <aside className="card case-chat-panel">
          <header className="case-chat-header">
            <div className="ai-heading-icon">
              <Icon name="sparkles" size={18} />
            </div>
            <div>
              <h3>Case Assistant</h3>
              <p>Answers grounded in selected case documents</p>
            </div>
            <button onClick={() => setChatStarted(false)} type="button">
              Clear chat
            </button>
          </header>
          <div className="chat-context-bar">
            <Icon name="briefcase" size={13} />
            <span>
              Working in <strong>{caseItem.title}</strong>
              <small>{caseItem.id} · 9 source documents</small>
            </span>
            <i>CASE CONTEXT</i>
          </div>

          <div className="case-chat-conversation">
            {chatStarted ? (
              <>
                <div className="chat-message user-message">
                  <span>AK</span>
                  <div>
                    <p>{userQuestion}</p>
                    <time>10:31 AM</time>
                  </div>
                </div>
                <div className="chat-message assistant-message">
                  <div className="assistant-avatar">
                    <Icon name="sparkles" size={14} />
                  </div>
                  <div>
                    <p>
                      The outstanding payment is mentioned in three case documents. The signed
                      agreement records the payment schedule, the final invoice states a claimed
                      balance of <strong>₹2,50,000</strong>, and the demand notice requests payment
                      within fifteen days.
                    </p>
                    <p className="assistant-caution">
                      The invoice amount is marked for review because it differs from an amount
                      referenced in the correspondence.
                    </p>
                    <time>Generated for lawyer review · 10:31 AM</time>
                    <div className="chat-source-cards">
                      {[
                        {
                          name: "Payment_Agreement.pdf",
                          page: 3,
                          passage: "Remaining balance payable by 20 February 2026.",
                        },
                        {
                          name: "Invoice_2026_014.pdf",
                          page: 1,
                          passage: "Outstanding balance shown as ₹2,50,000.",
                        },
                      ].map((source) => (
                        <article key={source.name}>
                          <div>
                            <Icon name="document" size={13} />
                            <span>
                              <strong>{source.name}</strong>
                              <small>Page {source.page}</small>
                            </span>
                          </div>
                          <p>“{source.passage}”</p>
                          <button onClick={() => onViewDocument(source.name)} type="button">
                            View Document <Icon name="chevron" size={12} />
                          </button>
                        </article>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-chat-state">
                <div>
                  <Icon name="message" size={22} />
                </div>
                <h4>Start a case-grounded conversation</h4>
                <p>Ask about facts, events, amounts or review items in this case.</p>
              </div>
            )}
          </div>

          <div className="suggested-question-section">
            <span>Suggested questions</span>
            <div>
              {suggestedQuestions.map((question) => (
                <button onClick={() => setInput(question)} key={question} type="button">
                  {question}
                </button>
              ))}
            </div>
          </div>
          <div className="chat-composer">
            <textarea
              aria-label="Ask about this case"
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask a question about this case..."
              value={input}
            />
            <button aria-label="Send message" onClick={sendMessage} type="button">
              <Icon name="chevron" size={17} />
            </button>
            <span>
              <Icon name="document" size={11} />
              Responses cite documents when sources are available.
            </span>
          </div>
        </aside>
      </div>
    </div>
  );
}

type ResearchProvision = {
  id: number;
  act: string;
  section: string;
  title: string;
  category: string;
  jurisdiction: string;
  description: string;
  relevance: string;
  reference: string;
  status: "Suggested for review" | "Reviewed by lawyer" | "Saved to case";
  elements: string[];
  documents: string[];
};

const illustrativeProvisions: ResearchProvision[] = [
  {
    id: 1,
    act: "Illustrative Commercial Transactions Framework",
    section: "Illustrative Section 12",
    title: "Written payment obligations",
    category: "Commercial",
    jurisdiction: "India — Illustrative",
    description:
      "Placeholder provision concerning written payment terms in a commercial supply arrangement.",
    relevance:
      "May help frame review of the written payment schedule and the disputed outstanding balance.",
    reference: "Illustrative research index · Demo record IR-102 · Not an authentic citation",
    status: "Suggested for review",
    elements: [
      "Written commercial arrangement",
      "Identifiable payment schedule",
      "Documented non-payment or short payment",
    ],
    documents: ["Payment_Agreement.pdf", "Invoice_2026_014.pdf"],
  },
  {
    id: 2,
    act: "Illustrative Civil Claims Procedure Guide",
    section: "Illustrative Section 8",
    title: "Pre-action demand notice",
    category: "Civil Procedure",
    jurisdiction: "Delhi — Illustrative",
    description:
      "Placeholder procedural text describing review of a demand notice before a civil payment claim.",
    relevance:
      "The case file includes a demand notice dated 12 March 2026 and a stated response period.",
    reference: "Illustrative procedure library · Demo record PR-208 · Not an authentic citation",
    status: "Reviewed by lawyer",
    elements: ["Clear statement of claim", "Specified response period", "Evidence of delivery"],
    documents: ["Demand_Notice.pdf", "Delivery_Receipt.pdf"],
  },
  {
    id: 3,
    act: "Illustrative Documentary Evidence Principles",
    section: "Illustrative Section 5",
    title: "Comparing inconsistent financial records",
    category: "Evidence",
    jurisdiction: "India — Illustrative",
    description:
      "Placeholder research note about comparing inconsistent amounts across documentary records.",
    relevance:
      "The invoice and correspondence contain different references to the balance allegedly outstanding.",
    reference: "Illustrative evidence digest · Demo record EV-315 · Not an authentic citation",
    status: "Saved to case",
    elements: [
      "Two or more documentary records",
      "Material inconsistency",
      "Source authenticity review",
    ],
    documents: ["Invoice_2026_014.pdf", "Payment_Agreement.pdf"],
  },
];

function ResearchStatusBadge({ status }: { status: ResearchProvision["status"] }) {
  const tone =
    status === "Saved to case"
      ? "saved"
      : status === "Reviewed by lawyer"
        ? "reviewed"
        : "suggested";
  return (
    <span className={`research-status ${tone}`}>
      <i />
      {status}
    </span>
  );
}

function LegalResearchPage({
  caseItem,
  onOverview,
  onDocuments,
  onTimeline,
  onEvidence,
  onLanguage,
  onAssistant,
  onSimilar,
  onViewDocument,
}: {
  caseItem: ManagedCase;
  onOverview: () => void;
  onDocuments: () => void;
  onTimeline: () => void;
  onEvidence: () => void;
  onLanguage: () => void;
  onAssistant: () => void;
  onSimilar: () => void;
  onViewDocument: (name: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [category, setCategory] = useState("All categories");
  const [jurisdiction, setJurisdiction] = useState("All jurisdictions");
  const [selectedId, setSelectedId] = useState(1);
  const [savedIds, setSavedIds] = useState<number[]>([3]);
  const [sourceOpen, setSourceOpen] = useState<ResearchProvision | null>(null);
  const [notes, setNotes] = useState(
    "Confirm the current text and effective date before using this reference.",
  );

  const results = useMemo(() => {
    const normalized = appliedQuery.trim().toLowerCase();
    return illustrativeProvisions.filter(
      (item) =>
        (!normalized ||
          `${item.act} ${item.section} ${item.title}`.toLowerCase().includes(normalized)) &&
        (category === "All categories" || item.category === category) &&
        (jurisdiction === "All jurisdictions" || item.jurisdiction === jurisdiction),
    );
  }, [appliedQuery, category, jurisdiction]);

  const selected =
    illustrativeProvisions.find((item) => item.id === selectedId) ?? illustrativeProvisions[0];
  const saveProvision = (id: number) =>
    setSavedIds((current) => (current.includes(id) ? current : [...current, id]));

  return (
    <div className="workspace-content research-content">
      <div className="workspace-breadcrumb">
        <button onClick={onOverview} type="button">
          My Cases
        </button>
        <Icon name="chevron" size={13} />
        <span>{caseItem.title}</span>
        <Icon name="chevron" size={13} />
        <span>Legal Research</span>
      </div>
      <section className="research-page-header">
        <div>
          <div className="eyebrow">CASE RESEARCH</div>
          <h2>Legal Research</h2>
          <p>Explore legal provisions potentially relevant to this case.</p>
          <div className="assistant-case-meta">
            <strong>{caseItem.title}</strong>
            <span>{caseItem.id}</span>
            <span>{caseItem.type}</span>
            <Badge status="Active" />
          </div>
        </div>
        <div className="research-header-mark">
          <Icon name="book" size={19} />
          <span>
            <strong>Illustrative research workspace</strong>
            <small>Placeholder references only</small>
          </span>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs research-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "Legal Research" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Overview") onOverview();
              if (tab === "Documents") onDocuments();
              if (tab === "Timeline") onTimeline();
              if (tab === "Evidence") onEvidence();
              if (tab === "Language Converter") onLanguage();
              if (tab === "AI Summary & Assistant") onAssistant();
              if (tab === "Similar Cases") onSimilar();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="research-disclaimer">
        <Icon name="help" size={14} />
        <span>
          Legal research suggestions are provided for reference. Verify the current law and
          applicability before relying on them.
        </span>
      </div>

      <section className="card research-search-card">
        <div className="research-search-row">
          <label className="case-search">
            <Icon name="search" size={17} />
            <input
              aria-label="Search legal provisions"
              placeholder="Search acts, sections, legal provisions..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") setAppliedQuery(query);
              }}
            />
          </label>
          <label className="filter-control">
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option>All categories</option>
              <option>Commercial</option>
              <option>Civil Procedure</option>
              <option>Evidence</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <label className="filter-control">
            <select value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}>
              <option>All jurisdictions</option>
              <option>India — Illustrative</option>
              <option>Delhi — Illustrative</option>
            </select>
            <Icon name="chevron" size={13} />
          </label>
          <button className="primary-button" onClick={() => setAppliedQuery(query)} type="button">
            <Icon name="search" size={15} />
            Search
          </button>
        </div>
        <div className="recent-provisions">
          <span>Recently viewed</span>
          {illustrativeProvisions.slice(0, 2).map((item) => (
            <button onClick={() => setSelectedId(item.id)} key={item.id} type="button">
              <Icon name="clock" size={11} />
              {item.section}
            </button>
          ))}
        </div>
      </section>

      <div className="research-layout">
        <section className="research-results-column">
          <div className="research-results-heading">
            <div>
              <h3>Relevant Provisions</h3>
              <p>{results.length} illustrative results · Review applicability independently</p>
            </div>
            <span>CASE CONTEXT</span>
          </div>
          {results.length ? (
            results.map((item) => {
              const isSaved = savedIds.includes(item.id);
              return (
                <article
                  className={`card provision-card ${selectedId === item.id ? "selected" : ""}`}
                  onClick={() => setSelectedId(item.id)}
                  key={item.id}
                >
                  <div className="provision-card-top">
                    <div className="provision-book-icon">
                      <Icon name="book" size={17} />
                    </div>
                    <div>
                      <span>{item.act}</span>
                      <h4>
                        {item.section} · {item.title}
                      </h4>
                    </div>
                    <ResearchStatusBadge status={isSaved ? "Saved to case" : item.status} />
                  </div>
                  <p>{item.description}</p>
                  <div className="provision-relevance">
                    <strong>Why it may be relevant</strong>
                    <span>{item.relevance}</span>
                  </div>
                  <div className="provision-reference">
                    <Icon name="document" size={12} />
                    <span>{item.reference}</span>
                  </div>
                  <footer>
                    <button
                      className={isSaved ? "saved-provision-button" : ""}
                      onClick={(event) => {
                        event.stopPropagation();
                        saveProvision(item.id);
                      }}
                      type="button"
                    >
                      <Icon name={isSaved ? "archive" : "plus"} size={13} />
                      {isSaved ? "Saved to Case" : "Save Provision"}
                    </button>
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedId(item.id);
                      }}
                      type="button"
                    >
                      View Details <Icon name="chevron" size={13} />
                    </button>
                  </footer>
                </article>
              );
            })
          ) : (
            <div className="card empty-research-state">
              <div>
                <Icon name="book" size={24} />
              </div>
              <h3>No illustrative provisions found</h3>
              <p>Try a broader placeholder search or clear the selected filters.</p>
              <button
                className="secondary-button"
                onClick={() => {
                  setQuery("");
                  setAppliedQuery("");
                  setCategory("All categories");
                  setJurisdiction("All jurisdictions");
                }}
                type="button"
              >
                Clear Search
              </button>
            </div>
          )}

          <section className="card saved-provisions-section">
            <header>
              <div>
                <h3>Saved Provisions</h3>
                <p>References saved by the lawyer for this case.</p>
              </div>
              <span>{savedIds.length} saved</span>
            </header>
            <div>
              {savedIds.length ? (
                illustrativeProvisions
                  .filter((item) => savedIds.includes(item.id))
                  .map((item) => (
                    <button onClick={() => setSelectedId(item.id)} key={item.id} type="button">
                      <div className="provision-book-icon">
                        <Icon name="book" size={14} />
                      </div>
                      <span>
                        <strong>{item.section}</strong>
                        <small>{item.act}</small>
                      </span>
                      <ResearchStatusBadge status="Saved to case" />
                      <Icon name="chevron" size={13} />
                    </button>
                  ))
              ) : (
                <p>No provisions saved to this case yet.</p>
              )}
            </div>
          </section>
        </section>

        <aside className="card provision-details-panel">
          <header>
            <div>
              <span>PROVISION DETAILS</span>
              <h3>{selected.section}</h3>
              <p>{selected.act}</p>
            </div>
            <ResearchStatusBadge
              status={savedIds.includes(selected.id) ? "Saved to case" : selected.status}
            />
          </header>
          <div className="provision-panel-body">
            <section>
              <h4>Placeholder Description</h4>
              <p>
                {selected.description} This demonstration text is not a reproduction of current law
                and must not be treated as legal authority.
              </p>
            </section>
            <section>
              <h4>Key Elements</h4>
              <ul>
                {selected.elements.map((element) => (
                  <li key={element}>
                    <i />
                    {element}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h4>Potential Connection to Case Facts</h4>
              <p>{selected.relevance}</p>
            </section>
            <section>
              <h4>Related Source Documents</h4>
              <div className="research-document-links">
                {selected.documents.map((document) => (
                  <button onClick={() => onViewDocument(document)} key={document} type="button">
                    <div className="document-file-icon">
                      <Icon name="document" size={14} />
                    </div>
                    <span>
                      <strong>{document}</strong>
                      <small>View case source</small>
                    </span>
                    <Icon name="chevron" size={13} />
                  </button>
                ))}
              </div>
            </section>
            <section>
              <h4>Lawyer Notes</h4>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
            </section>
            <button
              className="research-source-button"
              onClick={() => setSourceOpen(selected)}
              type="button"
            >
              <Icon name="book" size={14} />
              View illustrative source record
              <Icon name="chevron" size={13} />
            </button>
          </div>
          <footer>
            <button
              className="secondary-button"
              onClick={() => setSourceOpen(selected)}
              type="button"
            >
              View Source
            </button>
            <button
              className="primary-button"
              onClick={() => saveProvision(selected.id)}
              type="button"
            >
              {savedIds.includes(selected.id) ? "Saved to Case" : "Save to Case"}
            </button>
          </footer>
        </aside>
      </div>

      {sourceOpen && (
        <div className="modal-backdrop" onMouseDown={() => setSourceOpen(null)}>
          <div
            className="modal research-source-modal"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-head">
              <div>
                <h2>Illustrative Source Record</h2>
                <p>{sourceOpen.reference}</p>
              </div>
              <button className="icon-button" onClick={() => setSourceOpen(null)} type="button">
                <Icon name="close" size={18} />
              </button>
            </div>
            <div className="illustrative-source-notice">
              <Icon name="help" size={15} />
              <span>
                This is a fictional source-detail view for interface demonstration. It is not an
                authentic legal database record or citation.
              </span>
            </div>
            <article className="source-record-preview">
              <span>ILLUSTRATIVE EXAMPLE</span>
              <h3>{sourceOpen.act}</h3>
              <h4>
                {sourceOpen.section} — {sourceOpen.title}
              </h4>
              <p>{sourceOpen.description}</p>
              <p>
                Placeholder source text would appear here after connection to a verified legal
                research provider.
              </p>
            </article>
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={() => setSourceOpen(null)}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

type SimilarCaseRecord = {
  id: number;
  title: string;
  number: string;
  court: string;
  year: string;
  category: string;
  summary: string;
  similarity: number;
  provisions: string[];
  background: string;
  facts: string[];
  judgment: string;
  reference: string;
};

const illustrativeSimilarCases: SimilarCaseRecord[] = [
  {
    id: 1,
    title: "Rao Components v. Malhotra Distributors",
    number: "Illustrative Case IC-2024-117",
    court: "Illustrative Commercial Bench, Delhi",
    year: "2024",
    category: "Payment Dispute",
    summary:
      "Fictional dispute involving a written supply agreement, disputed invoice balance and demand notice.",
    similarity: 87,
    provisions: ["Illustrative Payment Terms §12", "Illustrative Notice Procedure §8"],
    background:
      "A fictional supplier sought recovery of an alleged unpaid balance after goods were delivered under a written arrangement.",
    facts: [
      "Written supply agreement recorded staged payments.",
      "Final invoice amount was disputed by the purchaser.",
      "A demand notice preceded the illustrative civil filing.",
    ],
    judgment:
      "Illustrative placeholder summary: the fictional court examined the signed agreement, invoices and proof of delivery before resolving the documentary dispute.",
    reference: "Demo judgment archive · Record SC-117 · Not an authentic judgment",
  },
  {
    id: 2,
    title: "Apex Wholesale v. Nanda Stores",
    number: "Illustrative Case IC-2023-084",
    court: "Illustrative Civil Court, New Delhi",
    year: "2023",
    category: "Contract Dispute",
    summary:
      "Fictional matter concerning inconsistent payment dates across an agreement and later correspondence.",
    similarity: 81,
    provisions: ["Illustrative Contract Records §6", "Illustrative Evidence Review §5"],
    background:
      "A fictional wholesaler and retailer disagreed about whether a revised payment date had been accepted.",
    facts: [
      "Agreement contained an original due date.",
      "Email correspondence referred to a later date.",
      "No signed amendment appeared in the fictional record.",
    ],
    judgment:
      "Illustrative placeholder summary: the fictional court compared contemporaneous records and party correspondence without creating a rule for the current case.",
    reference: "Demo judgment archive · Record SC-084 · Not an authentic judgment",
  },
  {
    id: 3,
    title: "Mehra Trading Co. v. Sethi Retail",
    number: "Illustrative Case IC-2022-209",
    court: "Illustrative District Commercial Court",
    year: "2022",
    category: "Invoice Dispute",
    summary: "Fictional invoice dispute involving partial payment and conflicting receipt amounts.",
    similarity: 74,
    provisions: ["Illustrative Documentary Evidence §5", "Illustrative Commercial Claims §14"],
    background:
      "A fictional trading company alleged that a retailer made only partial payment against multiple invoices.",
    facts: [
      "Receipt reflected a lower amount than the invoice total.",
      "Ledger entries required verification.",
      "Parties disputed allocation of the payment.",
    ],
    judgment:
      "Illustrative placeholder summary: the fictional decision reviewed the documentary chain and reconciliation records.",
    reference: "Demo judgment archive · Record SC-209 · Not an authentic judgment",
  },
  {
    id: 4,
    title: "Kapoor Supplies v. Arora Market House",
    number: "Illustrative Case IC-2021-156",
    court: "Illustrative High Court Commercial List",
    year: "2021",
    category: "Payment Dispute",
    summary:
      "Fictional case about delivery acknowledgment, outstanding invoices and a later legal notice.",
    similarity: 68,
    provisions: ["Illustrative Delivery Records §9", "Illustrative Demand Notice §8"],
    background:
      "A fictional supplier relied on delivery records and invoices in support of a payment claim.",
    facts: [
      "Delivery acknowledgment was partly illegible.",
      "Invoices identified an unpaid balance.",
      "Notice was issued after correspondence between the parties.",
    ],
    judgment:
      "Illustrative placeholder summary: the fictional court assessed source authenticity and evidentiary weight.",
    reference: "Demo judgment archive · Record SC-156 · Not an authentic judgment",
  },
];

function SimilarCasesPage({
  caseItem,
  onOverview,
  onDocuments,
  onTimeline,
  onEvidence,
  onLanguage,
  onAssistant,
  onResearch,
}: {
  caseItem: ManagedCase;
  onOverview: () => void;
  onDocuments: () => void;
  onTimeline: () => void;
  onEvidence: () => void;
  onLanguage: () => void;
  onAssistant: () => void;
  onResearch: () => void;
}) {
  const [query, setQuery] = useState("");
  const [court, setCourt] = useState("All courts");
  const [year, setYear] = useState("All years");
  const [category, setCategory] = useState("All categories");
  const [selectedId, setSelectedId] = useState(1);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return illustrativeSimilarCases.filter(
      (item) =>
        (!normalized ||
          `${item.title} ${item.number} ${item.provisions.join(" ")}`
            .toLowerCase()
            .includes(normalized)) &&
        (court === "All courts" || item.court === court) &&
        (year === "All years" || item.year === year) &&
        (category === "All categories" || item.category === category),
    );
  }, [category, court, query, year]);

  const selected =
    illustrativeSimilarCases.find((item) => item.id === selectedId) ?? illustrativeSimilarCases[0];
  const clearFilters = () => {
    setQuery("");
    setCourt("All courts");
    setYear("All years");
    setCategory("All categories");
  };

  return (
    <div className="workspace-content similar-content">
      <div className="workspace-breadcrumb">
        <button onClick={onOverview} type="button">
          My Cases
        </button>
        <Icon name="chevron" size={13} />
        <span>{caseItem.title}</span>
        <Icon name="chevron" size={13} />
        <span>Similar Cases</span>
      </div>
      <section className="similar-page-header">
        <div>
          <div className="eyebrow">ILLUSTRATIVE CASE COMPARISON</div>
          <h2>Similar Past Cases</h2>
          <p>Explore past judgments with potentially related facts.</p>
          <div className="assistant-case-meta">
            <strong>{caseItem.title}</strong>
            <span>{caseItem.id}</span>
            <span>{caseItem.type}</span>
            <Badge status="Active" />
          </div>
        </div>
        <div className="similar-header-mark">
          <Icon name="archive" size={19} />
          <span>
            <strong>4 illustrative records</strong>
            <small>Fictional examples for UI review</small>
          </span>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs similar-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "Similar Cases" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Overview") onOverview();
              if (tab === "Documents") onDocuments();
              if (tab === "Timeline") onTimeline();
              if (tab === "Evidence") onEvidence();
              if (tab === "Language Converter") onLanguage();
              if (tab === "AI Summary & Assistant") onAssistant();
              if (tab === "Legal Research") onResearch();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="similar-disclaimer">
        <Icon name="help" size={14} />
        <span>
          Similarity does not establish that a past judgment applies to the current case. Lawyers
          must independently verify relevance.
        </span>
      </div>

      <section className="card similar-search-card">
        <label className="case-search">
          <Icon name="search" size={17} />
          <input
            aria-label="Search similar cases"
            placeholder="Search by case name, keyword or legal provision..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="filter-control">
          <select value={court} onChange={(event) => setCourt(event.target.value)}>
            <option>All courts</option>
            {[...new Set(illustrativeSimilarCases.map((item) => item.court))].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control">
          <select value={year} onChange={(event) => setYear(event.target.value)}>
            <option>All years</option>
            <option>2024</option>
            <option>2023</option>
            <option>2022</option>
            <option>2021</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <label className="filter-control">
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option>All categories</option>
            <option>Payment Dispute</option>
            <option>Contract Dispute</option>
            <option>Invoice Dispute</option>
          </select>
          <Icon name="chevron" size={13} />
        </label>
        <button className="clear-filters" onClick={clearFilters} type="button">
          <Icon name="close" size={13} />
          Clear
        </button>
      </section>

      <div className="similar-layout">
        <section className="similar-results-column">
          <div className="similar-results-heading">
            <div>
              <h3>Potentially Related Cases</h3>
              <p>{results.length} fictional results · Similarity is illustrative only</p>
            </div>
            <span>SORTED BY SIMILARITY</span>
          </div>
          {results.length ? (
            results.map((item) => (
              <article
                className={`card similar-case-card ${selectedId === item.id ? "selected" : ""}`}
                onClick={() => setSelectedId(item.id)}
                key={item.id}
              >
                <div className="similarity-score">
                  <strong>{item.similarity}%</strong>
                  <span>Illustrative similarity</span>
                </div>
                <div className="similar-case-copy">
                  <span>FICTIONAL EXAMPLE</span>
                  <h4>{item.title}</h4>
                  <p className="case-number">{item.number}</p>
                  <div className="case-court-meta">
                    <span>
                      <Icon name="gavel" size={12} />
                      {item.court}
                    </span>
                    <span>
                      <Icon name="calendar" size={12} />
                      {item.year}
                    </span>
                  </div>
                  <p>{item.summary}</p>
                  <div className="case-provision-tags">
                    {item.provisions.map((provision) => (
                      <span key={provision}>{provision}</span>
                    ))}
                  </div>
                </div>
                <div className="similar-card-action">
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      setSelectedId(item.id);
                    }}
                    type="button"
                  >
                    View Case Details <Icon name="chevron" size={13} />
                  </button>
                </div>
              </article>
            ))
          ) : (
            <div className="card empty-similar-state">
              <div>
                <Icon name="archive" size={24} />
              </div>
              <h3>No illustrative cases found</h3>
              <p>Try changing the search terms or clearing the selected filters.</p>
              <button className="secondary-button" onClick={clearFilters} type="button">
                Clear Filters
              </button>
            </div>
          )}
        </section>

        <aside className="card similar-details-panel">
          <header>
            <div>
              <span>CASE DETAILS · FICTIONAL</span>
              <h3>{selected.title}</h3>
              <p>{selected.number}</p>
            </div>
            <div className="details-similarity">
              <strong>{selected.similarity}%</strong>
              <span>Illustrative</span>
            </div>
          </header>
          <div className="similar-panel-body">
            <div className="similar-court-line">
              <span>
                <Icon name="gavel" size={12} />
                {selected.court}
              </span>
              <span>
                <Icon name="calendar" size={12} />
                Judgment year {selected.year}
              </span>
            </div>
            <section>
              <h4>Case Background</h4>
              <p>{selected.background}</p>
            </section>
            <section>
              <h4>Key Facts</h4>
              <ul>
                {selected.facts.map((fact) => (
                  <li key={fact}>
                    <i />
                    {fact}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h4>Illustrative Judgment Summary</h4>
              <p>{selected.judgment}</p>
            </section>
            <section>
              <h4>Relevant Provisions</h4>
              <div className="details-provision-list">
                {selected.provisions.map((provision) => (
                  <span key={provision}>
                    <Icon name="book" size={11} />
                    {provision}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <h4>Source / Reference</h4>
              <div className="similar-source-reference">
                <Icon name="document" size={14} />
                <span>
                  <strong>{selected.reference}</strong>
                  <small>Placeholder record for frontend demonstration only</small>
                </span>
              </div>
            </section>
            <div className="panel-verification-note">
              <Icon name="help" size={14} />
              <span>
                Independently verify the judgment, current law and factual relevance before relying
                on this record.
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function LanguageConverterPage({
  caseItem,
  onOverview,
  onDocuments,
  onTimeline,
  onEvidence,
  onAssistant,
  onResearch,
  onSimilar,
  onViewDocument,
}: {
  caseItem: ManagedCase;
  onOverview: () => void;
  onDocuments: () => void;
  onTimeline: () => void;
  onEvidence: () => void;
  onAssistant: () => void;
  onResearch: () => void;
  onSimilar: () => void;
  onViewDocument: (name: string) => void;
}) {
  const [documentName, setDocumentName] = useState("Demand_Notice.pdf");
  const [sourceLanguage, setSourceLanguage] = useState<"Hindi" | "English">("Hindi");
  const [page, setPage] = useState(1);
  const [reviewed, setReviewed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const targetLanguage = sourceLanguage === "Hindi" ? "English" : "Hindi";
  const hindiText = (
    <>
      <h3>भुगतान की मांग हेतु विधिक सूचना</h3>
      <p>दिनांक: 12 मार्च 2026</p>
      <p>
        सेवा में,
        <br />
        <strong>वर्मा ट्रेडर्स</strong>
        <br />
        नई दिल्ली
      </p>
      <p>विषय: आपूर्ति समझौते के अंतर्गत बकाया भुगतान के संबंध में सूचना।</p>
      <p>
        महोदय, शर्मा एंटरप्राइजेज की ओर से आपको सूचित किया जाता है कि दिनांक 18 जनवरी 2026 को निष्पादित समझौते
        के अनुसार देय राशि का भुगतान पूर्ण रूप से प्राप्त नहीं हुआ है।
      </p>
      <p>
        हमारे अभिलेख के अनुसार <mark>₹2,50,000 की शेष राशि [अस्पष्ट अवधि]</mark> से बकाया है। आपसे अनुरोध है कि
        सूचना प्राप्ति के पंद्रह दिनों के भीतर भुगतान करें।
      </p>
      <p>यह पाठ केवल काल्पनिक प्रदर्शन डेटा है।</p>
    </>
  );
  const englishText = (
    <>
      <h3>Legal Notice Demanding Payment</h3>
      <p>Date: 12 March 2026</p>
      <p>
        To,
        <br />
        <strong>Verma Traders</strong>
        <br />
        New Delhi
      </p>
      <p>Subject: Notice concerning outstanding payment under the supply agreement.</p>
      <p>
        On behalf of Sharma Enterprises, you are informed that the amount due under the agreement
        executed on 18 January 2026 has not been received in full.
      </p>
      <p>
        According to our records, the balance of{" "}
        <mark>₹2,50,000 has remained due since [uncertain period]</mark>. You are requested to make
        payment within fifteen days of receiving this notice.
      </p>
      <p>This text is fictional demonstration data only.</p>
    </>
  );

  function changeDocument(name: string) {
    setDocumentName(name);
    setSourceLanguage(name === "Payment_Agreement.pdf" ? "English" : "Hindi");
    setPage(1);
    setReviewed(false);
  }

  const translatedPlainText =
    targetLanguage === "English"
      ? "Legal Notice Demanding Payment\n\nOn behalf of Sharma Enterprises, you are informed that the amount due under the agreement has not been received in full. The balance of ₹2,50,000 requires verification against the original document."
      : "भुगतान की मांग हेतु विधिक सूचना\n\nशर्मा एंटरप्राइजेज की ओर से आपको सूचित किया जाता है कि समझौते के अनुसार देय राशि का भुगतान पूर्ण रूप से प्राप्त नहीं हुआ है। ₹2,50,000 की शेष राशि का मूल दस्तावेज़ से सत्यापन आवश्यक है।";

  async function copyTranslation() {
    try {
      await navigator.clipboard?.writeText(translatedPlainText);
    } finally {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  function downloadTranslation() {
    const file = new Blob([translatedPlainText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(file);
    const link = window.document.createElement("a");
    link.href = url;
    link.download = `${documentName.replace(/\.[^.]+$/, "")}_${targetLanguage}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  }

  return (
    <div className="workspace-content converter-content">
      <div className="workspace-breadcrumb">
        <button onClick={onOverview} type="button">
          My Cases
        </button>
        <Icon name="chevron" size={13} />
        <span>{caseItem.title}</span>
        <Icon name="chevron" size={13} />
        <span>Language Converter</span>
      </div>
      <section className="converter-page-header">
        <div>
          <div className="eyebrow">DOCUMENT LANGUAGE TOOLS</div>
          <h2>Language Converter</h2>
          <p>Compare original Hindi and English legal document text within this case.</p>
          <div className="assistant-case-meta">
            <strong>{caseItem.title}</strong>
            <span>{caseItem.id}</span>
            <span>{caseItem.type}</span>
            <Badge status="Active" />
          </div>
        </div>
        <div className="converter-header-mark">
          <Icon name="book" size={19} />
          <span>
            <strong>Hindi ↔ English</strong>
            <small>Case document translation</small>
          </span>
        </div>
      </section>

      <nav aria-label="Case workspace" className="workspace-tabs converter-tabs">
        {[
          "Overview",
          "Documents",
          "Timeline",
          "Evidence",
          "Language Converter",
          "AI Summary & Assistant",
          "Legal Research",
          "Similar Cases",
        ].map((tab) => (
          <button
            className={tab === "Language Converter" ? "active" : ""}
            key={tab}
            onClick={() => {
              if (tab === "Overview") onOverview();
              if (tab === "Documents") onDocuments();
              if (tab === "Timeline") onTimeline();
              if (tab === "Evidence") onEvidence();
              if (tab === "AI Summary & Assistant") onAssistant();
              if (tab === "Legal Research") onResearch();
              if (tab === "Similar Cases") onSimilar();
            }}
            type="button"
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="translation-disclaimer">
        <Icon name="help" size={14} />
        <span>
          Translations are provided for assistance. Always verify important legal terminology
          against the original document.
        </span>
      </div>

      <section className="card converter-controls">
        <label className="converter-document-selector">
          <Icon name="document" size={16} />
          <span>
            <small>DOCUMENT</small>
            <select value={documentName} onChange={(event) => changeDocument(event.target.value)}>
              <option>Demand_Notice.pdf</option>
              <option>Payment_Agreement.pdf</option>
              <option>Delivery_Receipt.pdf</option>
            </select>
          </span>
          <Icon name="chevron" size={13} />
        </label>
        <div className="language-direction-control">
          <label>
            <small>SOURCE LANGUAGE</small>
            <select
              value={sourceLanguage}
              onChange={(event) => setSourceLanguage(event.target.value as "Hindi" | "English")}
            >
              <option>Hindi</option>
              <option>English</option>
            </select>
          </label>
          <button
            aria-label="Swap languages"
            onClick={() => setSourceLanguage(targetLanguage)}
            type="button"
          >
            <Icon name="chevron" size={16} />
            <Icon name="chevron" size={16} />
          </button>
          <label>
            <small>TARGET LANGUAGE</small>
            <select
              value={targetLanguage}
              onChange={(event) =>
                setSourceLanguage(event.target.value === "Hindi" ? "English" : "Hindi")
              }
            >
              <option>English</option>
              <option>Hindi</option>
            </select>
          </label>
        </div>
        <div className="translation-state">
          <span className="processing-status processed">Translation Ready</span>
          <span className={`review-status ${reviewed ? "verified" : "needs-review"}`}>
            {reviewed ? "Reviewed by Lawyer" : "Needs Review"}
          </span>
        </div>
      </section>

      <div className="translation-workspace">
        <section className="card translation-panel original-text-panel">
          <header className="translation-panel-header">
            <div>
              <span>ORIGINAL DOCUMENT</span>
              <h3>{sourceLanguage} Text</h3>
            </div>
            <div className="translation-page-controls">
              <button onClick={() => setPage(Math.max(1, page - 1))} type="button">
                <Icon name="chevron" size={14} />
              </button>
              <span>Page {page} of 3</span>
              <button onClick={() => setPage(Math.min(3, page + 1))} type="button">
                <Icon name="chevron" size={14} />
              </button>
            </div>
          </header>
          <div className={`translation-document-copy ${sourceLanguage.toLowerCase()}`}>
            {sourceLanguage === "Hindi" ? hindiText : englishText}
          </div>
          <footer className="translation-panel-footer">
            <button onClick={() => onViewDocument(documentName)} type="button">
              <Icon name="document" size={13} />
              <span>
                <strong>{documentName}</strong>
                <small>Original source → Page {page}</small>
              </span>
              <Icon name="chevron" size={13} />
            </button>
            <span className="source-authenticity">
              <i />
              Original document
            </span>
          </footer>
        </section>

        <section className="card translation-panel translated-text-panel">
          <header className="translation-panel-header">
            <div>
              <span>ASSISTED TRANSLATION</span>
              <h3>{targetLanguage} Translation</h3>
            </div>
            <div className="translation-actions">
              <button onClick={copyTranslation} type="button">
                <Icon name="document" size={13} />
                {copied ? "Copied" : "Copy"}
              </button>
              <button onClick={downloadTranslation} type="button">
                <Icon name="download" size={13} />
                {downloaded ? "Prepared" : "Download"}
              </button>
            </div>
          </header>
          <div className={`translation-document-copy ${targetLanguage.toLowerCase()}`}>
            {targetLanguage === "English" ? englishText : hindiText}
            <div className="uncertain-translation-note">
              <i />
              <span>
                <strong>Uncertain translation</strong>Amber text indicates terminology or OCR output
                requiring comparison with the original.
              </span>
            </div>
          </div>
          <footer className="translation-review-footer">
            <div>
              <span>Translation status</span>
              <strong>{reviewed ? "Lawyer reviewed" : "Awaiting lawyer review"}</strong>
            </div>
            <button
              className={reviewed ? "secondary-button reviewed-button" : "primary-button"}
              onClick={() => setReviewed(true)}
              type="button"
            >
              {reviewed ? "Reviewed" : "Mark as Reviewed"}
            </button>
          </footer>
        </section>
      </div>

      <section className="card translation-reference-bar">
        <div>
          <Icon name="document" size={15} />
          <span>
            <strong>Source traceability</strong>
            <small>
              {documentName} → Page {page} · {sourceLanguage} original
            </small>
          </span>
        </div>
        <button onClick={() => onViewDocument(documentName)} type="button">
          View Original Document <Icon name="chevron" size={13} />
        </button>
        <div>
          <span className="ocr-confidence">OCR 92%</span>
          <span className="review-status needs-review">Terminology Review</span>
        </div>
      </section>
    </div>
  );
}

const caseWorkspaceTabs: { label: string; page: PageName }[] = [
  { label: "Overview", page: "Case Workspace" },
  { label: "Documents", page: "Documents" },
  { label: "Timeline", page: "Case Timeline" },
  { label: "Evidence", page: "Case Evidence" },
  { label: "Language Converter", page: "Language Converter" },
  { label: "AI Summary & Assistant", page: "AI Case Summary & Assistant" },
  { label: "Legal Research", page: "Legal Research" },
  { label: "Similar Cases", page: "Similar Cases" },
];

function CaseWorkspaceLayout({
  caseItem,
  currentPage,
  onBack,
  onNavigate,
  children,
}: {
  caseItem: ManagedCase;
  currentPage: PageName;
  onBack: () => void;
  onNavigate: (page: PageName) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="case-route-shell">
      <div className="workspace-content shared-case-chrome">
        <div className="workspace-breadcrumb">
          <button onClick={onBack} type="button">
            My Cases
          </button>
          <Icon name="chevron" size={13} />
          <span>{caseItem.title}</span>
        </div>
        <section className="case-workspace-header">
          <div className="workspace-title-block">
            <div className="workspace-title-line">
              <h2>{caseItem.title}</h2>
              <Badge status={caseItem.status} />
            </div>
            <div className="workspace-case-meta">
              <span>{caseItem.id}</span>
              <i />
              <span>{caseItem.type}</span>
              <i />
              <span>Delhi High Court</span>
            </div>
            <p>Selected case workspace · Last updated {caseItem.updated.toLowerCase()}</p>
          </div>
          <div className="case-context-chip">
            <Icon name="briefcase" size={15} />
            <span>
              <small>ACTIVE SECTION</small>
              <strong>
                {caseWorkspaceTabs.find((tab) => tab.page === currentPage)?.label ?? "Overview"}
              </strong>
            </span>
          </div>
        </section>
        <nav aria-label="Case workspace" className="workspace-tabs shared-workspace-tabs">
          {caseWorkspaceTabs.map((tab) => (
            <button
              className={currentPage === tab.page ? "active" : ""}
              key={tab.page}
              onClick={() => onNavigate(tab.page)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="nested-case-section">{children}</div>
    </div>
  );
}

function FloatingAssistant({
  open,
  minimized,
  caseContext,
  caseItem,
  onOpen,
  onClose,
  onMinimize,
  onRestore,
  onExpand,
}: {
  open: boolean;
  minimized: boolean;
  caseContext: boolean;
  caseItem: ManagedCase;
  onOpen: () => void;
  onClose: () => void;
  onMinimize: () => void;
  onRestore: () => void;
  onExpand: () => void;
}) {
  const [input, setInput] = useState("");
  const [chatStarted, setChatStarted] = useState(true);
  const [question, setQuestion] = useState(
    caseContext ? "Which facts still need review in this case?" : "What can Sutra help me with?",
  );

  const suggestions = caseContext
    ? ["Summarise this case", "Which facts need review?", "Show important source documents"]
    : ["Find a case in my workspace", "How do I upload documents?", "What can I review today?"];

  function send() {
    if (!input.trim()) return;
    setQuestion(input.trim());
    setInput("");
    setChatStarted(true);
  }

  return (
    <>
      {open && (
        <aside
          id="floating-ai-assistant"
          className={`floating-ai-panel ${minimized ? "minimized" : ""}`}
          aria-label="Sutra AI Assistant"
        >
          <header className="floating-ai-header">
            <div className="floating-ai-avatar">
              <img src={sutraAssistantLogo} alt="Sutra AI Assistant" />
            </div>
            <div>
              <strong>Sutra AI</strong>
              <span>
                {caseContext ? "Case-aware assistant" : "Workspace assistant"}
                <i />
              </span>
            </div>
            <button
              className="new-chat-button"
              onClick={() => {
                setChatStarted(false);
                setQuestion("");
              }}
              type="button"
            >
              New Chat
            </button>
            <div className="floating-panel-controls">
              <button
                aria-label={minimized ? "Restore assistant" : "Minimise assistant"}
                onClick={minimized ? onRestore : onMinimize}
                type="button"
              >
                <Icon name={minimized ? "maximize" : "minus"} size={14} />
              </button>
              <button aria-label="Expand assistant" onClick={onExpand} type="button">
                <Icon name="maximize" size={14} />
              </button>
              <button aria-label="Close assistant" onClick={onClose} type="button">
                <Icon name="close" size={14} />
              </button>
            </div>
          </header>

          {!minimized && (
            <>
              <div className="floating-context-bar">
                <Icon name={caseContext ? "briefcase" : "dashboard"} size={13} />
                <span>
                  <strong>{caseContext ? caseItem.title : "General workspace"}</strong>
                  <small>
                    {caseContext ? `${caseItem.id} · Selected case context` : "No case selected"}
                  </small>
                </span>
                <i>{caseContext ? "CASE" : "GENERAL"}</i>
              </div>
              <div className="floating-conversation">
                {chatStarted ? (
                  <>
                    <div className="floating-message user">
                      <p>{question}</p>
                    </div>
                    <div className="floating-message assistant">
                      <div className="mini-ai-mark">
                        <img src={sutraAssistantLogo} alt="" />
                      </div>
                      <div>
                        <p>
                          {caseContext
                            ? "I found three items that still need lawyer review: the final invoice amount, the delivery acknowledgment signature, and a payment date referenced differently across two documents."
                            : "I can help you navigate Sutra, locate cases and documents, and organise your review workflow. Select a case when you want document-grounded assistance."}
                        </p>
                        {caseContext && (
                          <button type="button">
                            <Icon name="document" size={11} />
                            View 3 source references
                          </button>
                        )}
                        <time>Placeholder response · Verify before relying</time>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="floating-empty-chat">
                    <div className="mini-ai-mark large">
                      <img src={sutraAssistantLogo} alt="" />
                    </div>
                    <strong>How can I assist?</strong>
                    <span>
                      {caseContext
                        ? "Ask about the selected case and its documents."
                        : "Ask about your Sutra workspace."}
                    </span>
                  </div>
                )}
              </div>
              <div className="floating-suggestions">
                <span>Suggested</span>
                <div>
                  {suggestions.map((suggestion) => (
                    <button onClick={() => setInput(suggestion)} key={suggestion} type="button">
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
              <div className="floating-composer">
                <textarea
                  aria-label="Message Sutra AI"
                  placeholder={caseContext ? "Ask about this case..." : "Ask Sutra AI..."}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      send();
                    }
                  }}
                />
                <button aria-label="Send message" onClick={send} type="button">
                  <Icon name="chevron" size={17} />
                </button>
                <span>Frontend prototype · No AI service connected</span>
              </div>
            </>
          )}
        </aside>
      )}

      <button
        className={`floating-ai-orb ${open ? "active" : ""}`}
        aria-controls="floating-ai-assistant"
        aria-expanded={open}
        aria-label={open ? "Close Sutra AI Assistant" : "Open Sutra AI Assistant"}
        onClick={open ? onClose : onOpen}
        type="button"
      >
        <span className="orb-reflection" />
        <img src={sutraAssistantLogo} alt="Sutra AI" />
        <i />
      </button>
    </>
  );
}

function GlobalAIAssistantPage() {
  const [input, setInput] = useState("");
  const [question, setQuestion] = useState("What can you help me review today?");
  return (
    <div className="dashboard-content global-ai-page">
      <section className="global-ai-intro">
        <div>
          <div className="eyebrow">WORKSPACE ASSISTANT</div>
          <h2>AI Assistant</h2>
          <p>Navigate your workspace and organise legal review tasks.</p>
        </div>
        <div className="global-ai-brand">
          <img src={sutraAssistantLogo} alt="Sutra AI" />
          <span>
            <strong>Sutra AI</strong>
            <small>General workspace mode</small>
          </span>
        </div>
      </section>
      <div className="assistant-disclaimer">
        <Icon name="help" size={14} />
        <span>
          AI-generated responses are for lawyer review. Verify information against original
          documents before relying on it.
        </span>
      </div>
      <section className="card global-ai-workspace">
        <div className="global-ai-sidebar">
          <div className="new-conversation-card">
            <div className="mini-ai-mark large">
              <img src={sutraAssistantLogo} alt="" />
            </div>
            <strong>New conversation</strong>
            <span>General questions about your Sutra workspace.</span>
          </div>
          <button className="active" type="button">
            <Icon name="message" size={14} />
            Current conversation
          </button>
          <button type="button">
            <Icon name="clock" size={14} />
            Recent conversations
          </button>
        </div>
        <div className="global-ai-chat">
          <header>
            <div>
              <strong>General workspace assistant</strong>
              <span>No case context selected</span>
            </div>
            <span className="ai-label">FRONTEND PROTOTYPE</span>
          </header>
          <div className="global-ai-messages">
            <div className="chat-message user-message">
              <span>AK</span>
              <div>
                <p>{question}</p>
                <time>Just now</time>
              </div>
            </div>
            <div className="chat-message assistant-message">
              <div className="assistant-avatar">
                <img src={sutraAssistantLogo} alt="" />
              </div>
              <div>
                <p>
                  I can help you locate cases and documents, understand your review queue, or
                  navigate Sutra. Open an individual case for document-grounded assistance.
                </p>
                <time>Placeholder response · No AI service connected</time>
              </div>
            </div>
          </div>
          <div className="global-ai-composer">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about your workspace..."
            />
            <button
              onClick={() => {
                if (input.trim()) {
                  setQuestion(input.trim());
                  setInput("");
                }
              }}
              type="button"
            >
              <Icon name="chevron" size={17} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function SettingsPage() {
  const [appearance, setAppearance] = useState("System");
  const [language, setLanguage] = useState("English");
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [reviewReminders, setReviewReminders] = useState(true);
  const [securityAlerts, setSecurityAlerts] = useState(true);

  return (
    <div className="dashboard-content settings-page">
      <section className="settings-intro">
        <div>
          <div className="eyebrow">PREFERENCES</div>
          <h2>Settings</h2>
          <p>Manage your Sutra account, appearance and security preferences.</p>
        </div>
        <span>Changes are saved locally for this prototype</span>
      </section>
      <div className="settings-layout">
        <nav className="card settings-section-nav">
          {[
            ["Account Settings", "users"],
            ["Appearance", "dashboard"],
            ["Language Preferences", "book"],
            ["Notifications", "bell"],
            ["Privacy & Security", "settings"],
          ].map(([label, icon]) => (
            <a href={`#${label.toLowerCase().replaceAll(" ", "-")}`} key={label}>
              <Icon name={icon as IconName} size={15} />
              {label}
            </a>
          ))}
        </nav>
        <div className="settings-sections">
          <section className="card settings-card" id="account-settings">
            <header>
              <div className="settings-card-icon">
                <Icon name="users" size={17} />
              </div>
              <div>
                <h3>Account Settings</h3>
                <p>Basic profile and professional details.</p>
              </div>
            </header>
            <div className="settings-form-grid">
              <label>
                <span>Full name</span>
                <input value={`Adv. ${currentUser.name}`} readOnly />
              </label>
              <label>
                <span>Email address</span>
                <input value={currentUser.email} readOnly />
              </label>
              <label>
                <span>Role</span>
                <input value={currentUser.role} readOnly />
              </label>
              <label>
                <span>Bar registration</span>
                <input value="DL/2014/1842" readOnly />
              </label>
            </div>
            <footer>
              <button className="primary-button" type="button">
                Save Account
              </button>
            </footer>
          </section>

          <section className="card settings-card" id="appearance">
            <header>
              <div className="settings-card-icon">
                <Icon name="dashboard" size={17} />
              </div>
              <div>
                <h3>Appearance</h3>
                <p>Choose how Sutra appears on this device.</p>
              </div>
            </header>
            <div className="settings-option-row">
              <div>
                <strong>Interface theme</strong>
                <span>The neumorphic system theme remains active in this prototype.</span>
              </div>
              <div className="segmented-setting">
                {["Light", "System", "Dark"].map((option) => (
                  <button
                    className={appearance === option ? "active" : ""}
                    onClick={() => setAppearance(option)}
                    key={option}
                    type="button"
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="card settings-card" id="language-preferences">
            <header>
              <div className="settings-card-icon">
                <Icon name="book" size={17} />
              </div>
              <div>
                <h3>Language Preferences</h3>
                <p>Set your interface and document-review language.</p>
              </div>
            </header>
            <div className="settings-option-row">
              <div>
                <strong>Preferred interface language</strong>
                <span>Document languages remain independent of this setting.</span>
              </div>
              <label className="filter-control settings-select">
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  <option>English</option>
                  <option>Hindi</option>
                </select>
                <Icon name="chevron" size={13} />
              </label>
            </div>
          </section>

          <section className="card settings-card" id="notifications">
            <header>
              <div className="settings-card-icon">
                <Icon name="bell" size={17} />
              </div>
              <div>
                <h3>Notifications</h3>
                <p>Control workspace updates and review reminders.</p>
              </div>
            </header>
            <div className="settings-toggle-list">
              <SettingsToggle
                checked={emailNotifications}
                label="Email notifications"
                note="Receive case and document updates by email."
                onChange={setEmailNotifications}
              />
              <SettingsToggle
                checked={reviewReminders}
                label="Review reminders"
                note="Remind me about items awaiting lawyer review."
                onChange={setReviewReminders}
              />
              <SettingsToggle
                checked={securityAlerts}
                label="Security alerts"
                note="Notify me about important account activity."
                onChange={setSecurityAlerts}
              />
            </div>
          </section>

          <section className="card settings-card" id="privacy-&-security">
            <header>
              <div className="settings-card-icon">
                <Icon name="settings" size={17} />
              </div>
              <div>
                <h3>Privacy & Security</h3>
                <p>Review access and account protection controls.</p>
              </div>
            </header>
            <div className="security-actions">
              <div>
                <strong>Password</strong>
                <span>Last updated 42 days ago</span>
                <button className="secondary-button" type="button">
                  Change Password
                </button>
              </div>
              <div>
                <strong>Two-step verification</strong>
                <span>Additional account protection is enabled</span>
                <button className="secondary-button" type="button">
                  Manage
                </button>
              </div>
              <div>
                <strong>Active sessions</strong>
                <span>2 signed-in devices</span>
                <button className="secondary-button" type="button">
                  Review Sessions
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function SettingsToggle({
  checked,
  label,
  note,
  onChange,
}: {
  checked: boolean;
  label: string;
  note: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <div>
      <span>
        <strong>{label}</strong>
        <small>{note}</small>
      </span>
      <button
        aria-pressed={checked}
        className={`settings-switch ${checked ? "active" : ""}`}
        onClick={() => onChange(!checked)}
        type="button"
      >
        <i />
      </button>
    </div>
  );
}

const helpTopics = [
  {
    title: "Getting Started",
    description: "Set up your workspace, create a case and invite your team.",
    icon: "home" as IconName,
    articles: "6 articles",
  },
  {
    title: "Document Upload & Translation",
    description: "Upload files, review OCR and compare Hindi-English translations.",
    icon: "document" as IconName,
    articles: "9 articles",
  },
  {
    title: "Timeline & Evidence",
    description: "Review extracted events, evidence and original source references.",
    icon: "timeline" as IconName,
    articles: "8 articles",
  },
  {
    title: "AI Assistant",
    description: "Use case-grounded assistance and understand source-linked responses.",
    icon: "sparkles" as IconName,
    articles: "5 articles",
  },
];

function HelpSupportPage() {
  const [search, setSearch] = useState("");
  const [openFaq, setOpenFaq] = useState(0);
  const [requestOpen, setRequestOpen] = useState(false);
  const filteredTopics = helpTopics.filter((topic) =>
    `${topic.title} ${topic.description}`.toLowerCase().includes(search.toLowerCase()),
  );
  const faqs = [
    [
      "How do I open a Case Workspace?",
      "Open My Cases and select a case name. Its documents, timeline, evidence and other tools remain within the shared workspace.",
    ],
    [
      "Can Sutra verify legal information automatically?",
      "No. Extracted information, translations and assistant responses require independent lawyer verification.",
    ],
    [
      "Which document formats are supported?",
      "The current frontend demonstrates PDF, DOCX, PNG and JPG upload states.",
    ],
    [
      "How do I view an original source?",
      "Use View Source or View Original Document wherever a source reference appears.",
    ],
  ];

  return (
    <div className="dashboard-content help-page">
      <section className="help-hero">
        <div>
          <div className="eyebrow">SUTRA SUPPORT</div>
          <h2>Help & Support</h2>
          <p>Find guidance for cases, documents, review tools and your account.</p>
        </div>
        <label className="case-search help-search">
          <Icon name="search" size={17} />
          <input
            aria-label="Search help articles"
            placeholder="Search help articles..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </section>
      <section className="help-topic-grid">
        {filteredTopics.map((topic) => (
          <article className="card help-topic-card" key={topic.title}>
            <div className="help-topic-icon">
              <Icon name={topic.icon} size={18} />
            </div>
            <div>
              <h3>{topic.title}</h3>
              <p>{topic.description}</p>
              <span>{topic.articles}</span>
            </div>
            <button aria-label={`Open ${topic.title}`} type="button">
              <Icon name="chevron" size={14} />
            </button>
          </article>
        ))}
      </section>
      {!filteredTopics.length && (
        <div className="card help-empty-state">
          <Icon name="search" size={22} />
          <strong>No help articles found</strong>
          <span>Try a broader search phrase.</span>
        </div>
      )}
      <div className="help-lower-grid">
        <section className="card faq-card">
          <header>
            <div>
              <h3>Frequently Asked Questions</h3>
              <p>Quick answers about using Sutra.</p>
            </div>
            <Icon name="help" size={18} />
          </header>
          <div>
            {faqs.map(([question, answer], index) => (
              <article className={openFaq === index ? "open" : ""} key={question}>
                <button onClick={() => setOpenFaq(openFaq === index ? -1 : index)} type="button">
                  <span>{question}</span>
                  <Icon name="chevron" size={14} />
                </button>
                {openFaq === index && <p>{answer}</p>}
              </article>
            ))}
          </div>
        </section>
        <aside className="card contact-support-card">
          <div className="contact-support-icon">
            <Icon name="message" size={20} />
          </div>
          <h3>Contact Support</h3>
          <p>
            Need help that is not covered in the guides? Send a request to the Sutra support team.
          </p>
          <dl>
            <div>
              <dt>Typical response</dt>
              <dd>Within one business day</dd>
            </div>
            <div>
              <dt>Support hours</dt>
              <dd>Mon–Fri, 9:00–18:00 IST</dd>
            </div>
          </dl>
          <button className="primary-button" onClick={() => setRequestOpen(true)} type="button">
            Submit Support Request
          </button>
        </aside>
      </div>
      {requestOpen && (
        <div className="modal-backdrop" onMouseDown={() => setRequestOpen(false)}>
          <div
            className="modal support-request-modal"
            onMouseDown={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="modal-head">
              <div>
                <h2>Submit Support Request</h2>
                <p>Describe the issue using fictional prototype information only.</p>
              </div>
              <button className="icon-button" onClick={() => setRequestOpen(false)} type="button">
                <Icon name="close" size={18} />
              </button>
            </div>
            <label className="field-label">Topic</label>
            <select className="field-input">
              <option>General question</option>
              <option>Documents & translation</option>
              <option>Timeline & evidence</option>
              <option>Account access</option>
            </select>
            <label className="field-label">Message</label>
            <textarea placeholder="How can the support team help?" />
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={() => setRequestOpen(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => setRequestOpen(false)}
                type="button"
              >
                Submit Request
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileDetailsModal({
  onClose,
  onSettings,
}: {
  onClose: () => void;
  onSettings: () => void;
}) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal profile-details-modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-head">
          <div>
            <h2>My Profile</h2>
            <p>Your Sutra account overview.</p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="profile-modal-identity">
          <div className="avatar profile-large">{currentUser.initials}</div>
          <div>
            <strong>Adv. {currentUser.name}</strong>
            <span>{currentUser.role}</span>
            <small>{currentUser.email}</small>
          </div>
        </div>
        <dl className="profile-modal-details">
          <div>
            <dt>Organisation</dt>
            <dd>Khanna Legal Chambers</dd>
          </div>
          <div>
            <dt>Bar registration</dt>
            <dd>DL/2014/1842</dd>
          </div>
          <div>
            <dt>Workspace role</dt>
            <dd>Administrator</dd>
          </div>
        </dl>
        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose} type="button">
            Close
          </button>
          <button className="primary-button" onClick={onSettings} type="button">
            Open Settings
          </button>
        </div>
      </div>
    </div>
  );
}

function LogoutConfirmationModal({
  onClose,
  onConfirm,
}: {
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal logout-confirmation-modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="modal-head">
          <div>
            <h2>Log out of Sutra?</h2>
            <p>You will need to sign in again to access your workspace.</p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="logout-warning">
          <Icon name="help" size={17} />
          <span>Any unsaved prototype changes may be lost.</span>
        </div>
        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="logout-button" onClick={onConfirm} type="button">
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

function SignInPage({ onSignIn }: { onSignIn: () => void }) {
  return (
    <main className="sign-in-page">
      <section className="sign-in-card">
        <img src={sutraLogo} alt="Sutra" />
        <div className="sign-in-heading">
          <div className="eyebrow">SECURE WORKSPACE</div>
          <h1>Sign in to Sutra</h1>
          <p>Access your cases, documents and legal review workspace.</p>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSignIn();
          }}
        >
          <label>
            <span>Email address</span>
            <input type="email" defaultValue={currentUser.email} required />
          </label>
          <label>
            <span>Password</span>
            <input type="password" defaultValue="sutra-demo" required />
          </label>
          <div className="sign-in-options">
            <label>
              <input type="checkbox" defaultChecked />
              <span>Remember me</span>
            </label>
            <button type="button">Forgot password?</button>
          </div>
          <button className="primary-button" type="submit">
            Sign In
          </button>
        </form>
        <p className="sign-in-demo-note">
          <Icon name="help" size={13} />
          Frontend demonstration — no credentials are transmitted.
        </p>
      </section>
    </main>
  );
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageName>("Language Converter");
  const [selectedCase, setSelectedCase] = useState<ManagedCase>(initialManagedCases[0]);
  const [selectedDocument, setSelectedDocument] = useState<ManagedDocument>(managedDocuments[2]);
  const [previewReturnPage, setPreviewReturnPage] = useState<
    | "Documents"
    | "Case Timeline"
    | "Case Evidence"
    | "AI Case Summary & Assistant"
    | "Legal Research"
    | "Language Converter"
  >("Documents");
  const [query, setQuery] = useState("");
  const [cases, setCases] = useState(initialCases);
  const [managedCases, setManagedCases] = useState(initialManagedCases);
  const [showNewCase, setShowNewCase] = useState(false);
  const [showDocumentUpload, setShowDocumentUpload] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantMinimized, setAssistantMinimized] = useState(false);
  const [profileDetailsOpen, setProfileDetailsOpen] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);

  const hasCaseContext = ![
    "Dashboard",
    "My Cases",
    "AI Assistant",
    "Settings",
    "Help & Support",
  ].includes(currentPage);

  function pathForPage(page: PageName, caseId = selectedCase.id) {
    const encodedCaseId = encodeURIComponent(caseId);
    const casePaths: Partial<Record<PageName, string>> = {
      "Case Workspace": "overview",
      Documents: "documents",
      "Case Timeline": "timeline",
      "Case Evidence": "evidence",
      "Language Converter": "language-converter",
      "AI Case Summary & Assistant": "assistant",
      "Legal Research": "legal-research",
      "Similar Cases": "similar-cases",
      "Document Preview": "documents/preview",
    };
    if (page === "Dashboard") return "/dashboard";
    if (page === "My Cases") return "/cases";
    if (page === "AI Assistant") return "/assistant";
    if (page === "Settings") return "/settings";
    if (page === "Help & Support") return "/help";
    if (page === "Sign In") return "/sign-in";
    return `/cases/${encodedCaseId}/${casePaths[page] ?? "overview"}`;
  }

  function navigateTo(page: PageName, caseOverride?: ManagedCase) {
    if (caseOverride) setSelectedCase(caseOverride);
    setCurrentPage(page);
    const nextPath = pathForPage(page, caseOverride?.id ?? selectedCase.id);
    if (window.location.pathname !== nextPath) window.history.pushState({}, "", nextPath);
  }

  useEffect(() => {
    document.title = `Sutra ${currentPage}`;
  }, [currentPage]);

  useEffect(() => {
    const routeFromLocation = () => {
      const path = window.location.pathname;
      if (path === "/dashboard") return setCurrentPage("Dashboard");
      if (path === "/cases") return setCurrentPage("My Cases");
      if (path === "/assistant") return setCurrentPage("AI Assistant");
      if (path === "/settings") return setCurrentPage("Settings");
      if (path === "/help") return setCurrentPage("Help & Support");
      if (path === "/sign-in") return setCurrentPage("Sign In");
      const match = path.match(/^\/cases\/([^/]+)\/([^/]+)(?:\/([^/]+))?/);
      if (!match) return;
      const caseId = decodeURIComponent(match[1]);
      const matchedCase = managedCases.find((item) => item.id === caseId);
      if (matchedCase) setSelectedCase(matchedCase);
      const section = match[2];
      const routeMap: Record<string, PageName> = {
        overview: "Case Workspace",
        documents: match[3] === "preview" ? "Document Preview" : "Documents",
        timeline: "Case Timeline",
        evidence: "Case Evidence",
        "language-converter": "Language Converter",
        assistant: "AI Case Summary & Assistant",
        "legal-research": "Legal Research",
        "similar-cases": "Similar Cases",
      };
      if (routeMap[section]) setCurrentPage(routeMap[section]);
    };

    if (window.location.pathname === "/") {
      window.history.replaceState({}, "", pathForPage(currentPage));
    } else {
      routeFromLocation();
    }
    window.addEventListener("popstate", routeFromLocation);
    return () => window.removeEventListener("popstate", routeFromLocation);
    // Route setup is intentionally registered once; navigation updates state directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredCases = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return cases;
    return cases.filter((item) =>
      [item.id, item.title, item.type, item.status].some((value) =>
        value.toLowerCase().includes(normalized),
      ),
    );
  }, [cases, query]);

  function createCase(title: string, type: string) {
    if (currentPage === "My Cases") {
      setManagedCases((current) => [
        {
          id: `CT-2026-${String(current.length + 1).padStart(3, "0")}`,
          title,
          type,
          opposingParty: "Not yet added",
          documents: 0,
          updated: "Just now",
          status: "Active",
        },
        ...current,
      ]);
    } else {
      setCases((current) => [
        {
          id: `CT-2025-${String(85 + current.length).padStart(3, "0")}`,
          title,
          type,
          updated: "Just now",
          status: "Active",
        },
        ...current,
      ]);
    }
    setShowNewCase(false);
  }

  if (currentPage === "Sign In") {
    return <SignInPage onSignIn={() => navigateTo("Dashboard")} />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        active={
          currentPage === "Document Preview" && previewReturnPage === "Case Evidence"
            ? "Case Evidence"
            : currentPage === "Document Preview" &&
                previewReturnPage === "AI Case Summary & Assistant"
              ? "AI Case Summary & Assistant"
              : currentPage === "Document Preview" && previewReturnPage === "Legal Research"
                ? "Legal Research"
                : currentPage === "Document Preview" && previewReturnPage === "Language Converter"
                  ? "Language Converter"
                  : currentPage
        }
        onNavigate={(page) => {
          navigateTo(page);
        }}
        onLogout={() => setLogoutOpen(true)}
        onProfile={() => setProfileDetailsOpen(true)}
      />

      <main className="main-shell">
        <header className="topbar">
          <div className="mobile-brand">
            <img className="mobile-logo" src={sutraLogo} alt="Sutra" />
          </div>
          <h1>{currentPage}</h1>
          <div className="topbar-actions">
            <label className="global-search">
              <Icon name="search" size={18} />
              <input
                aria-label="Search cases and documents"
                onChange={(event) => setQuery(event.target.value)}
                placeholder={
                  currentPage === "Documents" ? "Search documents..." : "Search cases, documents..."
                }
                value={query}
              />
              <kbd>⌘ K</kbd>
            </label>
            <div className="notification-wrap">
              <button
                aria-label="Notifications"
                className="icon-button notification-button"
                onClick={() => setShowNotifications((current) => !current)}
                type="button"
              >
                <Icon name="bell" size={19} />
                <span className="notification-dot" />
              </button>
              {showNotifications && (
                <div className="notification-panel">
                  <div className="panel-title">
                    Notifications <span>2 new</span>
                  </div>
                  <p>
                    <strong>Review due today</strong>
                    <br />6 extracted events need your review.
                  </p>
                  <p>
                    <strong>Hearing reminder</strong>
                    <br />
                    ABC Traders hearing is in 3 days.
                  </p>
                </div>
              )}
            </div>
            {currentPage === "Dashboard" && (
              <button
                className="primary-button new-case-button"
                onClick={() => setShowNewCase(true)}
                type="button"
              >
                <Icon name="plus" size={18} strokeWidth={2.2} />
                New Case
              </button>
            )}
            {currentPage === "Documents" && (
              <button
                className="primary-button new-case-button"
                onClick={() => setShowDocumentUpload(true)}
                type="button"
              >
                <Icon name="plus" size={18} strokeWidth={2.2} />
                Upload Documents
              </button>
            )}
          </div>
        </header>

        {currentPage === "Dashboard" ? (
          <div className="dashboard-content">
            <section className="welcome-row">
              <div>
                <div className="eyebrow">MONDAY, 16 JUNE</div>
                <h2>Good morning, Adv. {currentUser.name}.</h2>
                <p>Here’s an overview of your cases and recent activity.</p>
              </div>
              <div className="demo-note">
                <span />
                Demo workspace data
              </div>
            </section>

            <section aria-label="Case overview" className="kpi-grid">
              {kpis.map((item) => (
                <article className="kpi-card" key={item.label}>
                  <div className={`kpi-icon ${item.tone}`}>
                    <Icon name={item.icon} size={19} />
                  </div>
                  <div className="kpi-copy">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small className={item.tone}>
                      <span className="indicator-dot" />
                      {item.note}
                    </small>
                  </div>
                </article>
              ))}
            </section>

            <div className="dashboard-grid">
              <section className="card cases-card">
                <div className="card-heading">
                  <div>
                    <h3>Active Cases</h3>
                    <p>Monitor your current matters and review status.</p>
                  </div>
                  <button className="text-button" type="button">
                    View all cases <Icon name="chevron" size={15} />
                  </button>
                </div>
                <div className="table-wrap">
                  <table>
                    <colgroup>
                      <col className="case-id-column" />
                      <col className="case-title-column" />
                      <col className="case-type-column" />
                      <col className="case-updated-column" />
                      <col className="case-status-column" />
                      <col className="case-action-column" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>Case ID</th>
                        <th>Case title</th>
                        <th>Case type</th>
                        <th>Last updated</th>
                        <th>Status</th>
                        <th>
                          <span className="sr-only">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCases.map((caseItem) => (
                        <tr key={caseItem.id}>
                          <td>
                            <span className="case-id">{caseItem.id}</span>
                          </td>
                          <td>
                            <strong className="case-title">{caseItem.title}</strong>
                          </td>
                          <td>{caseItem.type}</td>
                          <td>{caseItem.updated}</td>
                          <td>
                            <Badge status={caseItem.status} />
                          </td>
                          <td>
                            <button
                              aria-label={`Open ${caseItem.title}`}
                              className="row-action"
                              type="button"
                            >
                              <Icon name="chevron" size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                      {filteredCases.length === 0 && (
                        <tr>
                          <td className="empty-state" colSpan={6}>
                            No cases match “{query}”.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="review-reminder">
                  <Icon name="help" size={15} />
                  Extracted facts and events are suggestions and require lawyer verification.
                </div>
              </section>

              <div className="right-column">
                <section className="card hearings-card">
                  <div className="card-heading compact">
                    <div>
                      <h3>Upcoming Hearings</h3>
                      <p>Your next scheduled court dates.</p>
                    </div>
                    <button aria-label="Open calendar" className="icon-button subtle" type="button">
                      <Icon name="calendar" size={18} />
                    </button>
                  </div>
                  <div className="hearing-list">
                    {hearings.map((hearing) => (
                      <article className="hearing-item" key={hearing.title}>
                        <div className="date-tile">
                          <span>{hearing.month}</span>
                          <strong>{hearing.day}</strong>
                        </div>
                        <div className="hearing-copy">
                          <h4>{hearing.title}</h4>
                          <p>{hearing.court}</p>
                          <div className="hearing-meta">
                            <span>
                              <Icon name="clock" size={13} />
                              {hearing.time}
                            </span>
                            <Badge status={hearing.status} />
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                  <button className="full-text-button" type="button">
                    View hearing calendar
                  </button>
                </section>

                <section className="card activity-card">
                  <div className="card-heading compact">
                    <div>
                      <h3>Recent Activity</h3>
                      <p>Updates across your workspace.</p>
                    </div>
                    <button className="text-button" type="button">
                      View all
                    </button>
                  </div>
                  <div className="activity-list">
                    {activities.map((activity, index) => (
                      <div className="activity-item" key={activity.subject}>
                        <div className={`activity-icon ${activity.tone}`}>
                          <Icon name={activity.icon} size={15} />
                        </div>
                        <div className="activity-copy">
                          <strong>{activity.text}</strong>
                          <span>{activity.subject}</span>
                        </div>
                        <time>{activity.time}</time>
                        {index < activities.length - 1 && <div className="activity-line" />}
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          </div>
        ) : currentPage === "My Cases" ? (
          <MyCasesPage
            cases={managedCases}
            onCreateCase={() => setShowNewCase(true)}
            onOpenCase={(caseItem) => {
              navigateTo("Case Workspace", caseItem);
            }}
          />
        ) : currentPage === "Case Workspace" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <CaseWorkspace
              caseItem={selectedCase}
              onBack={() => navigateTo("My Cases")}
              onOpenDocuments={() => navigateTo("Documents")}
              onOpenTimeline={() => navigateTo("Case Timeline")}
              onOpenEvidence={() => navigateTo("Case Evidence")}
              onOpenLanguage={() => navigateTo("Language Converter")}
              onOpenAssistant={() => navigateTo("AI Case Summary & Assistant")}
              onOpenResearch={() => navigateTo("Legal Research")}
              onOpenSimilar={() => navigateTo("Similar Cases")}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Case Timeline" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <CaseTimelinePage
              caseItem={selectedCase}
              onViewSource={(timelineEvent) => {
                const sourceName = timelineEvent.source.split(" — ")[0];
                setSelectedDocument(
                  managedDocuments.find((document) => document.name === sourceName) ?? {
                    name: sourceName,
                    caseName: selectedCase.title,
                    type: "Source Document",
                    language: "English",
                    size: "1.6 MB",
                    date: "20 Mar 2026",
                    status: "Needs Review",
                  },
                );
                setPreviewReturnPage("Case Timeline");
                navigateTo("Document Preview");
              }}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Case Evidence" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <CaseEvidencePage
              caseItem={selectedCase}
              onViewSource={(evidenceItem) => {
                setSelectedDocument(
                  managedDocuments.find((document) => document.name === evidenceItem.source) ?? {
                    name: evidenceItem.source,
                    caseName: selectedCase.title,
                    type: evidenceItem.category,
                    language: "English",
                    size: "1.6 MB",
                    date: evidenceItem.date,
                    status: evidenceItem.status === "Verified" ? "Processed" : "Needs Review",
                  },
                );
                setPreviewReturnPage("Case Evidence");
                navigateTo("Document Preview");
              }}
              onOverview={() => navigateTo("Case Workspace")}
              onDocuments={() => navigateTo("Documents")}
              onViewTimeline={() => navigateTo("Case Timeline")}
              onLanguage={() => navigateTo("Language Converter")}
              onAssistant={() => navigateTo("AI Case Summary & Assistant")}
              onResearch={() => navigateTo("Legal Research")}
              onSimilar={() => navigateTo("Similar Cases")}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "AI Case Summary & Assistant" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <AICaseAssistantPage
              caseItem={selectedCase}
              onOverview={() => navigateTo("Case Workspace")}
              onDocuments={() => navigateTo("Documents")}
              onTimeline={() => navigateTo("Case Timeline")}
              onEvidence={() => navigateTo("Case Evidence")}
              onLanguage={() => navigateTo("Language Converter")}
              onResearch={() => navigateTo("Legal Research")}
              onSimilar={() => navigateTo("Similar Cases")}
              onViewDocument={(name) => {
                setSelectedDocument(
                  managedDocuments.find((document) => document.name === name) ?? {
                    name,
                    caseName: selectedCase.title,
                    type: "Case Document",
                    language: "English",
                    size: "1.5 MB",
                    date: "Today",
                    status: "Needs Review",
                  },
                );
                setPreviewReturnPage("AI Case Summary & Assistant");
                navigateTo("Document Preview");
              }}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Legal Research" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <LegalResearchPage
              caseItem={selectedCase}
              onOverview={() => navigateTo("Case Workspace")}
              onDocuments={() => navigateTo("Documents")}
              onTimeline={() => navigateTo("Case Timeline")}
              onEvidence={() => navigateTo("Case Evidence")}
              onLanguage={() => navigateTo("Language Converter")}
              onAssistant={() => navigateTo("AI Case Summary & Assistant")}
              onSimilar={() => navigateTo("Similar Cases")}
              onViewDocument={(name) => {
                setSelectedDocument(
                  managedDocuments.find((document) => document.name === name) ?? {
                    name,
                    caseName: selectedCase.title,
                    type: "Case Document",
                    language: "English",
                    size: "1.5 MB",
                    date: "Today",
                    status: "Needs Review",
                  },
                );
                setPreviewReturnPage("Legal Research");
                navigateTo("Document Preview");
              }}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Similar Cases" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <SimilarCasesPage
              caseItem={selectedCase}
              onOverview={() => navigateTo("Case Workspace")}
              onDocuments={() => navigateTo("Documents")}
              onTimeline={() => navigateTo("Case Timeline")}
              onEvidence={() => navigateTo("Case Evidence")}
              onLanguage={() => navigateTo("Language Converter")}
              onAssistant={() => navigateTo("AI Case Summary & Assistant")}
              onResearch={() => navigateTo("Legal Research")}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Language Converter" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <LanguageConverterPage
              caseItem={selectedCase}
              onOverview={() => navigateTo("Case Workspace")}
              onDocuments={() => navigateTo("Documents")}
              onTimeline={() => navigateTo("Case Timeline")}
              onEvidence={() => navigateTo("Case Evidence")}
              onAssistant={() => navigateTo("AI Case Summary & Assistant")}
              onResearch={() => navigateTo("Legal Research")}
              onSimilar={() => navigateTo("Similar Cases")}
              onViewDocument={(name) => {
                setSelectedDocument(
                  managedDocuments.find((document) => document.name === name) ?? {
                    name,
                    caseName: selectedCase.title,
                    type: "Case Document",
                    language: name === "Payment_Agreement.pdf" ? "English" : "Hindi",
                    size: "2.0 MB",
                    date: "Today",
                    status: "Needs Review",
                  },
                );
                setPreviewReturnPage("Language Converter");
                navigateTo("Document Preview");
              }}
            />
          </CaseWorkspaceLayout>
        ) : currentPage === "Settings" ? (
          <SettingsPage />
        ) : currentPage === "Help & Support" ? (
          <HelpSupportPage />
        ) : currentPage === "AI Assistant" ? (
          <GlobalAIAssistantPage />
        ) : currentPage === "Documents" ? (
          <CaseWorkspaceLayout
            caseItem={selectedCase}
            currentPage={currentPage}
            onBack={() => navigateTo("My Cases")}
            onNavigate={navigateTo}
          >
            <DocumentsPage
              caseContext={selectedCase.title}
              onOpenDocument={(document) => {
                setSelectedDocument(document);
                setPreviewReturnPage("Documents");
                navigateTo("Document Preview");
              }}
              onUpload={() => setShowDocumentUpload(true)}
            />
          </CaseWorkspaceLayout>
        ) : (
          <DocumentPreview
            document={selectedDocument}
            onBack={() => navigateTo(previewReturnPage)}
          />
        )}
      </main>

      {showNewCase && <NewCaseDialog onClose={() => setShowNewCase(false)} onCreate={createCase} />}
      {showDocumentUpload && <UploadDocumentsModal onClose={() => setShowDocumentUpload(false)} />}
      {profileDetailsOpen && (
        <ProfileDetailsModal
          onClose={() => setProfileDetailsOpen(false)}
          onSettings={() => {
            setProfileDetailsOpen(false);
            navigateTo("Settings");
          }}
        />
      )}
      {logoutOpen && (
        <LogoutConfirmationModal
          onClose={() => setLogoutOpen(false)}
          onConfirm={() => {
            setLogoutOpen(false);
            setAssistantOpen(false);
            setAssistantMinimized(false);
            navigateTo("Sign In");
          }}
        />
      )}
      <FloatingAssistant
        caseContext={hasCaseContext}
        caseItem={selectedCase}
        minimized={assistantMinimized}
        onClose={() => {
          setAssistantOpen(false);
          setAssistantMinimized(false);
        }}
        onExpand={() => {
          setAssistantOpen(false);
          setAssistantMinimized(false);
          navigateTo(hasCaseContext ? "AI Case Summary & Assistant" : "AI Assistant");
        }}
        onMinimize={() => setAssistantMinimized(true)}
        onOpen={() => {
          setAssistantOpen(true);
          setAssistantMinimized(false);
        }}
        onRestore={() => setAssistantMinimized(false)}
        open={assistantOpen}
      />
    </div>
  );
}
