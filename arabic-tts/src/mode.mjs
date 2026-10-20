// Fusha vs Saudi white detection from lexical markers (same lists as the skill).
const SAUDI = ['وش', 'إيش', 'ايش', 'ليش', 'وين', 'الحين', 'أبغى', 'ابغى', 'أبي', 'تبي', 'تبغى', 'يبغى', 'مو', 'بس', 'مرة', 'اللي', 'هذي', 'هذول', 'بكرة', 'زين', 'خلاص', 'يلا', 'شوي', 'عشان', 'لين', 'راح', 'كذا', 'معليش', 'طيب', 'رايح', 'رايك', 'ولا'];
const FUSHA = ['إن', 'إنّ', 'سوف', 'لن', 'لم', 'ليس', 'الذي', 'التي', 'الذين', 'هذه', 'ماذا', 'لماذا', 'أين', 'كيف', 'حيث', 'إذ', 'قد', 'ثم', 'ثمّ'];
const strip = (w) => w.replace(/[ً-ْٰـ]/g, '').replace(/[.!?؟،,;؛:…«»"()]/g, '');

export function detectMode(text) {
  const words = text.split(/\s+/).map(strip).map(w => w.replace(/^[وف]/, '')).filter(Boolean);
  let s = 0, f = 0;
  for (const w of words) { if (SAUDI.includes(w)) s++; if (FUSHA.includes(w)) f++; }
  // case endings (tanween) on several words point to fusha
  const tanween = (text.match(/[ً-ٍ]/g) || []).length;
  if (tanween >= 2 && s === 0) f++;
  return s >= 1 && s >= f ? 'saudi' : 'fusha';
}
