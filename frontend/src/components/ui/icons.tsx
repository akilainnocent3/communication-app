/**
 * App icon set: TailGrids icons at a consistent default size plus a few mail-specific glyphs TailGrids lacks.
 * Icons are decorative by default (aria-hidden); give the surrounding control an accessible label.
 */
import * as T from "@tailgrids/icons";
import type { SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement> & { size?: number };
type IconComponent = (props: IconProps) => React.ReactElement;

function sized(Component: React.FC<IconProps>, size = 18): IconComponent {
  const Icon = (props: IconProps) => <Component size={size} aria-hidden="true" focusable="false" {...props} />;
  Icon.displayName = Component.displayName || "Icon";
  return Icon;
}

function glyph(paths: React.ReactNode, name: string): IconComponent {
  const Icon = ({ size = 18, ...props }: IconProps) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>
      {paths}
    </svg>
  );
  Icon.displayName = name;
  return Icon;
}

export const SearchIcon = sized(T.Search1);
export const MailIcon = sized(T.Envelope1);
export const SendIcon = sized(T.Send1);
export const StarIcon = sized(T.StarIcon);
export const TrashIcon = sized(T.Trash1);
export const ArchiveIcon = sized(T.BoxArchive1);
export const ReplyIcon = sized(T.Reply);
export const ReplyAllIcon = sized(T.ReplyAll);
export const AttachmentIcon = sized(T.Paperclip2);
export const PencilIcon = sized(T.PenToSquare);
export const ClockIcon = sized(T.ClockThree);
export const CalendarIcon = sized(T.CalendarTime);
export const DashboardIcon = sized(T.DashboardSquare1);
export const UsersIcon = sized(T.UserMultiple1);
export const UserIcon = sized(T.User2);
export const BuildingIcon = sized(T.Buildings11);
export const LayersIcon = sized(T.Layers2);
export const PlugIcon = sized(T.Plug1);
export const ShieldIcon = sized(T.Shield1Check);
export const GearIcon = sized(T.Gear1);
export const FilterIcon = sized(T.Funnel1);
export const FileIcon = sized(T.FileText);
export const PdfIcon = sized(T.FileFormatPdf);
export const ImageIcon = sized(T.FileImage);
export const DownloadIcon = sized(T.Download1);
export const UploadIcon = sized(T.UploadCloud);
export const PrinterIcon = sized(T.Printer);
export const CodeIcon = sized(T.Code1);
export const RefreshIcon = sized(T.Reload);
export const PlusIcon = sized(T.Plus);
export const MinusIcon = sized(T.Minus);
export const CloseIcon = sized(T.Close);
export const CheckIcon = sized(T.Check);
export const CheckCircleIcon = sized(T.CheckCircle1);
export const DoubleCheckIcon = sized(T.DoubleCheckMark);
export const ErrorIcon = sized(T.ErrorCircle);
export const InfoIcon = sized(T.InfoCircle);
export const WarningIcon = sized(T.InfoTriangle);
export const ChevronDownIcon = sized(T.ChevronDown, 16);
export const ChevronUpIcon = sized(T.ChevronUp, 16);
export const ChevronLeftIcon = sized(T.ChevronLeft, 16);
export const ChevronRightIcon = sized(T.ChevronRight, 16);
export const ArrowLeftIcon = sized(T.ArrowLeft);
export const MenuIcon = sized(T.MenuHamburger1, 22);
export const DotsVerticalIcon = sized(T.MenuKebab1);
export const DotsIcon = sized(T.MenuMeatballs1);
export const SunIcon = sized(T.Sun1);
export const MoonIcon = sized(T.MoonHalfLeft5);
export const LogoutIcon = sized(T.Exit);
export const LinkIcon = sized(T.Link1AngularRight);
export const CopyIcon = sized(T.Copy1);
export const WhatsappIcon = sized(T.Whatsapp);
export const GoogleIcon = sized(T.Google);
export const EyeIcon = sized(T.Eye);
export const EyeOffIcon = sized(T.EyeDisabled);
export const KeyboardIcon = sized(T.Keyboard);
export const CommandIcon = sized(T.Command);
export const NoteIcon = sized(T.Comment1Dots);
export const PhoneIcon = sized(T.Telephone1);
export const MessageIcon = sized(T.Message1);
export const MediaIcon = sized(T.MultipleImages);
export const LockIcon = sized(T.Locked3);
export const GlobeIcon = sized(T.Globe2);
export const ExpandIcon = sized(T.ExpandSquare4);
export const ExternalIcon = sized(T.ExpandArrowTopRightSquare1);
export const SlidersIcon = sized(T.SlidersDoubleHorizontal);
export const SparkleIcon = sized(T.Sparkle);
export const ChartIcon = sized(T.BarChartSquare);
export const BellOffIcon = sized(T.BellDisabled2);
export const PinIcon = sized(T.Pin);

export const InboxIcon = glyph(<><path d="M3 13h4.5l1.5 3h6l1.5-3H21" /><path d="M5.5 5h13L21 13v5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18v-5z" /></>, "InboxIcon");
export const TagIcon = glyph(<><path d="M3 12V4.5A1.5 1.5 0 0 1 4.5 3H12l9 9-9 9z" /><circle cx="7.5" cy="7.5" r="1.25" /></>, "TagIcon");
export const ImportantIcon = glyph(<path d="M3 6h12.5l5 6-5 6H3l4.5-6z" />, "ImportantIcon");
export const SnoozeIcon = glyph(<><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2.5M4 4 7 2M20 4l-3-2" /></>, "SnoozeIcon");
export const SpamIcon = glyph(<><path d="M8.5 2.5h7l5 5v7l-5 5h-7l-5-5v-7z" /><path d="M12 7.5v5M12 16h.01" /></>, "SpamIcon");
export const ForwardIcon = glyph(<><path d="m15 5 6 6-6 6" /><path d="M21 11H9a6 6 0 0 0-6 6v2" /></>, "ForwardIcon");
export const UnreadIcon = glyph(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6 8.5 7 8.5-7" /></>, "UnreadIcon");
export const ReadIcon = glyph(<><path d="M3 10.5 12 4l9 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19z" /><path d="m3.5 11 8.5 6 8.5-6" /></>, "ReadIcon");
export const DraftIcon = glyph(<><path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></>, "DraftIcon");
export const AllMailIcon = glyph(<><rect x="5" y="7" width="16" height="12" rx="1.5" /><path d="M3 15V5.5A1.5 1.5 0 0 1 4.5 4H17M5.5 8l7.5 5.5L20.5 8" /></>, "AllMailIcon");
export const AssignIcon = glyph(<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 11l2 2 4-4" /></>, "AssignIcon");
export const TemplateIcon = glyph(<><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" /></>, "TemplateIcon");
export const SignatureIcon = glyph(<><path d="M3 17c3-1 4-9 6-9s-1 9 1.5 9 2.5-4 4-4 1 3 2.5 3H21" /><path d="M3 21h18" /></>, "SignatureIcon");
export const VacationIcon = glyph(<><path d="M12 21V11M12 11c-4 0-7 2-8 4 2-5 5-7 8-7s6 2 8 7c-1-2-4-4-8-4z" /><path d="M12 8c0-2 1-4 3-5" /></>, "VacationIcon");
export const MuteIcon = glyph(<><path d="M11 5 6 9H3v6h3l5 4z" /><path d="m16 9 5 6M21 9l-5 6" /></>, "MuteIcon");
export const UnsubscribeIcon = glyph(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6 8.5 7 8.5-7M4 20 20 4" /></>, "UnsubscribeIcon");
export const SplitIcon = glyph(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M10 4v16" /></>, "SplitIcon");
export const NoSplitIcon = glyph(<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18" /></>, "NoSplitIcon");
export const OfflineIcon = glyph(<><path d="M2 8.5a15 15 0 0 1 4-2.4M9.5 5.2A15 15 0 0 1 22 8.5M5 12a10 10 0 0 1 3.5-2M13 9.6a10 10 0 0 1 6 2.4M8.5 15.5a5 5 0 0 1 7 0M12 19h.01M3 3l18 18" /></>, "OfflineIcon");
export const SmartphoneIcon = glyph(<><rect x="6.5" y="2.5" width="11" height="19" rx="2" /><path d="M10.5 18.5h3" /></>, "SmartphoneIcon");
export const BlockIcon = glyph(<><circle cx="12" cy="12" r="9" /><path d="m5.7 5.7 12.6 12.6" /></>, "BlockIcon");
export const OutboxIcon = glyph(<><path d="M3 13h4.5l1.5 3h6l1.5-3H21" /><path d="M5.5 10 3 13v5a1.5 1.5 0 0 0 1.5 1.5h15A1.5 1.5 0 0 0 21 18v-5l-2.5-3" /><path d="M12 11V3M9 6l3-3 3 3" /></>, "OutboxIcon");
export const QrIcon = glyph(<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3" /></>, "QrIcon");

// --- Calls ------------------------------------------------------------------------------------------------------
const HANDSET = "M5 4h3.2l1.6 4-2 1.3a10.6 10.6 0 0 0 5 5l1.3-2 4 1.6V17a2 2 0 0 1-2.2 2A15.6 15.6 0 0 1 3 6.2 2 2 0 0 1 5 4z";
export const CallIncomingIcon = glyph(<><path d={HANDSET} /><path d="M21 3l-5.5 5.5M15.5 4v4.5H20" /></>, "CallIncomingIcon");
export const CallOutgoingIcon = glyph(<><path d={HANDSET} /><path d="M15.5 8.5L21 3M16.5 3H21v4.5" /></>, "CallOutgoingIcon");
export const CallMissedIcon = glyph(<><path d={HANDSET} /><path d="M15 3l6 6M21 3l-6 6" /></>, "CallMissedIcon");
export const CallbackIcon = glyph(<><path d={HANDSET} /><path d="M14.5 6.5a4 4 0 0 1 6.5 2.5M21 5v4h-4" /></>, "CallbackIcon");
export const LiveIcon = glyph(<><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8" /></>, "LiveIcon");
export const MoonClockIcon = glyph(<><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" /><path d="M14 8v3l2 1" /></>, "MoonClockIcon");
export const CoinsIcon = glyph(<><ellipse cx="9" cy="7" rx="5" ry="2.5" /><path d="M4 7v5c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5V7" /><path d="M10 17c.8 1.2 2.8 2 5 2 2.8 0 5-1.1 5-2.5v-5c0-1.4-2.2-2.5-5-2.5" /></>, "CoinsIcon");
