"""Bounded CSS candidates followed by observed hover/focus visibility changes."""

from dataclasses import dataclass

from playwright.async_api import Page
from playwright.async_api import TimeoutError as BrowserTimeout
from pydantic import BaseModel, ConfigDict, Field

from Asgard.Freya.Responsive.models.responsive_models import (
    MobileCompatibilityIssue,
    MobileCompatibilityIssueType,
)


class HoverCandidate(BaseModel):
    model_config = ConfigDict(strict=True)
    trigger: str = Field(max_length=4096)
    target: str = Field(max_length=4096)
    rule: str = Field(max_length=4096)
    declared_alternative: bool


class HoverInventory(BaseModel):
    model_config = ConfigDict(strict=True)
    candidates: list[HoverCandidate] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)


@dataclass
class HoverAssessment:
    issues: list[MobileCompatibilityIssue]
    limitations: list[str]


# The traversal caps bound both DOM/rule work and browser interaction count.
# Unreadable or unsupported CSS is unknown coverage, never an empty success.
INVENTORY_SCRIPT = r"""() => {
    const limitations = new Set(), candidates = [], rules = [], nodes = [];
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
    let node = walker.currentNode;
    while (node && nodes.length < 2000) {
        nodes.push(node);
        if (node.shadowRoot) limitations.add('shadow_dom_unassessed');
        if (node.localName === 'iframe') limitations.add('frame_content_unassessed');
        node = walker.nextNode();
    }
    if (node) limitations.add('element_limit');
    let visitedRules = 0;
    const seenSheets = new Set();
    function visit(list) {
        for (const rule of list) {
            if (++visitedRules > 2000) { limitations.add('rule_limit'); return; }
            if (rule.selectorText) {
                if (rule.selectorText.includes(':hover')) rules.push(rule.selectorText);
            } else if (rule.type === CSSRule.IMPORT_RULE) {
                sheet(rule.styleSheet);
            } else if (rule.cssRules) {
                if (rule.type === CSSRule.MEDIA_RULE && !matchMedia(rule.conditionText).matches) continue;
                if (rule.type === CSSRule.SUPPORTS_RULE && !CSS.supports(rule.conditionText)) continue;
                if (![CSSRule.MEDIA_RULE, CSSRule.SUPPORTS_RULE, CSSRule.LAYER_BLOCK_RULE].includes(rule.type)) {
                    limitations.add('unsupported_rule'); continue;
                }
                visit(rule.cssRules);
            }
        }
    }
    function sheet(value) {
        if (!value || seenSheets.has(value)) return;
        seenSheets.add(value);
        if (seenSheets.size > 200) { limitations.add('stylesheet_limit'); return; }
        if (value.disabled || (value.media.mediaText && !matchMedia(value.media.mediaText).matches)) return;
        try { visit(value.cssRules); } catch { limitations.add('unreadable_stylesheet'); }
    }
    for (const value of document.styleSheets) sheet(value);
    function path(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        const parts = [];
        while (el && el.nodeType === 1) {
            let index = 1, sibling = el.previousElementSibling;
            while (sibling) { index++; sibling = sibling.previousElementSibling; }
            parts.unshift(el.localName + ':nth-child(' + index + ')');
            el = el.parentElement;
        }
        return parts.join(' > ');
    }
    function visible(el) {
        const style = getComputedStyle(el), rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
               Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
    }
    const seen = new Set();
    for (const group of rules) {
        if (group.length > 4096 || group.includes('(')) { limitations.add('unsupported_selector'); continue; }
        for (const rule of group.split(',')) {
            if (!rule.includes(':hover')) continue;
            if ((rule.match(/:hover/g) || []).length !== 1) { limitations.add('unsupported_selector'); continue; }
            const [prefix, suffix] = rule.split(':hover');
            if (!prefix.trim() || /[+~]/.test(suffix)) { limitations.add('unsupported_selector'); continue; }
            for (const target of nodes) {
                let trigger;
                try {
                    if (!target.matches(rule.replace(':hover', '')) || visible(target)) continue;
                    trigger = target.closest(prefix.trim());
                } catch { limitations.add('unsupported_selector'); continue; }
                if (!trigger || !visible(trigger)) continue;
                const targetPath = path(target), triggerPath = path(trigger);
                const key = triggerPath + '\n' + targetPath;
                if (seen.has(key)) continue;
                if (candidates.length === 20) { limitations.add('candidate_limit'); continue; }
                seen.add(key);
                const control = trigger.closest('[onclick], [ontouchstart], [ontouchend], [aria-controls]');
                candidates.push({trigger: triggerPath, target: targetPath, rule: rule.trim(),
                                 declared_alternative: !!control});
            }
        }
    }
    if (candidates.length && document.scripts.length) limitations.add('script_interactions_unassessed');
    return {candidates, limitations: [...limitations]};
}"""

_VISIBLE = "el => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) !== 0 && r.width > 0 && r.height > 0; }"


async def assess_hover_dependencies(page: Page) -> HoverAssessment:
    """Observe hover reveal without activating arbitrary click/touch controls.

    Findings describe this fixture's CSS/hover/focus evidence. Dynamic event
    handlers and declared click alternatives remain unverified coverage.
    """
    await page.mouse.move(-1, -1)
    inventory = HoverInventory.model_validate(await page.evaluate(INVENTORY_SCRIPT))
    limitations = set(inventory.limitations)
    issues = []
    for candidate in inventory.candidates:
        trigger, target = page.locator(candidate.trigger), page.locator(candidate.target)
        try:
            await page.mouse.move(-1, -1)
            if await target.evaluate(_VISIBLE, timeout=500):
                limitations.add("candidate_state_changed")
                continue
            await trigger.hover(timeout=500)
            if not await target.evaluate(_VISIBLE, timeout=500):
                continue
            await page.mouse.move(-1, -1)
            # Focus the trigger or a reachable child control; never click it.
            focus_target = trigger
            if not await trigger.evaluate(
                "el => el.matches('a[href],button,input,select,textarea,[tabindex]')", timeout=500
            ):
                focus_target = trigger.locator("a[href],button,input,select,textarea,[tabindex]").first
            if await focus_target.count():
                await focus_target.focus(timeout=500)
                if await target.evaluate(_VISIBLE, timeout=500):
                    await focus_target.evaluate("el => el.blur()", timeout=500)
                    continue
                await focus_target.evaluate("el => el.blur()", timeout=500)
            if candidate.declared_alternative:
                limitations.add("declared_click_or_touch_alternative_unverified")
                continue
            issues.append(
                MobileCompatibilityIssue(
                    issue_type=MobileCompatibilityIssueType.HOVER_DEPENDENT,
                    element_selector=candidate.target,
                    description=f"Hovering {candidate.trigger} revealed hidden content matching {candidate.rule}; no focus reveal or declarative click/touch alternative was observed",
                    severity="moderate",
                    suggested_fix="Verify keyboard and touch access; this bounded heuristic does not prove universal inaccessibility",
                    affected_devices=[],
                )
            )
        except BrowserTimeout:
            limitations.add("interaction_timeout")
        finally:
            await page.mouse.move(-1, -1)
    return HoverAssessment(issues, sorted(limitations))
