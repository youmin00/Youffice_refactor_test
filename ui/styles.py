"""YOUFFICE 화면의 공통 스타일을 제공합니다."""

import streamlit as st


GLOBAL_STYLES = """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 82% 0%, rgba(75, 215, 179, 0.08), transparent 28%),
            var(--background-color);
    }

    [data-testid="stMainBlockContainer"] {
        max-width: 1840px !important;
        padding: 4.75rem 1.35rem 2rem !important;
    }

    section[data-testid="stSidebar"] {
        width: 270px !important;
        min-width: 270px !important;
        border-right: 1px solid rgba(128, 128, 128, 0.13);
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 0.8rem;
    }

    .youffice-brand {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        margin-bottom: 0.65rem;
    }

    .youffice-logo {
        display: grid;
        place-items: center;
        width: 38px;
        height: 38px;
        border-radius: 12px;
        background: rgba(88, 101, 242, 0.14);
        font-size: 1.25rem;
    }

    .youffice-brand-name {
        font-size: 1rem;
        font-weight: 750;
        line-height: 1.15;
    }

    .youffice-brand-subtitle {
        margin-top: 0.15rem;
        color: #7b8190;
        font-size: 0.72rem;
    }

    .youffice-meta {
        display: flex;
        gap: 0.4rem;
        margin-bottom: 1.15rem;
    }

    .youffice-chip {
        padding: 0.25rem 0.55rem;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 999px;
        background: rgba(128, 128, 128, 0.08);
        font-size: 0.7rem;
    }

    .st-key-project-selector-wrap {
        position: relative;
    }

    .project-name-hover-anchor {
        display: grid;
        grid-template-rows: 0fr;
        overflow: hidden;
        transition: grid-template-rows 0.18s ease, margin-top 0.18s ease;
    }

    .project-name-hover-card {
        position: static;
        min-height: 0;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        padding: 0 0.7rem;
        border: 1px solid rgba(128, 128, 128, 0.3);
        border-width: 0;
        border-radius: 9px;
        background: var(--secondary-background-color);
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.24);
        overflow-wrap: anywhere;
        color: var(--text-color);
        font-size: 0.82rem;
        font-weight: 650;
        line-height: 1.25;
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
        transform: translateY(-4px);
        transition:
            opacity 0.18s ease,
            transform 0.18s ease,
            visibility 0.18s ease,
            padding 0.18s ease;
    }

    .st-key-project-selector-wrap:hover .project-name-hover-anchor {
        grid-template-rows: 1fr;
        margin-top: 0.35rem;
    }

    .st-key-project-selector-wrap:hover .project-name-hover-card {
        padding: 0.55rem 0.7rem;
        border-width: 1px;
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
    }

    .org-title {
        margin-bottom: 0.75rem;
        font-size: 0.9rem;
        font-weight: 700;
    }

    .org-group-title {
        margin: 0.9rem 0 0.35rem 0.35rem;
        color: #8b90a0;
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.08em;
    }

    .employee-card {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        min-height: 54px;
        margin-bottom: 0.28rem;
        padding: 0.45rem 0.55rem;
        border-radius: 9px;
    }

    .employee-card.active {
        background: rgba(88, 101, 242, 0.12);
    }

    .employee-avatar {
        position: relative;
        display: grid;
        flex: 0 0 40px;
        place-items: center;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: rgba(128, 128, 128, 0.13);
        font-size: 1rem;
    }

    .employee-avatar img {
        width: 100%;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
        object-position: center 28%;
    }

    .employee-copy {
        min-width: 0;
    }

    .employee-card.active .employee-avatar {
        background: #5865f2;
    }

    .status-dot {
        position: absolute;
        right: -1px;
        bottom: -1px;
        width: 10px;
        height: 10px;
        border: 2px solid var(--secondary-background-color);
        border-radius: 50%;
        background: #8b90a0;
    }

    .employee-card.active .status-dot {
        background: #23a55a;
    }

    .employee-name {
        overflow: hidden;
        font-size: 0.83rem;
        font-weight: 650;
        line-height: 1.2;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .employee-status {
        margin-top: 0.15rem;
        color: #8b90a0;
        font-size: 0.68rem;
    }

    .employee-card.active .employee-status {
        color: #23a55a;
    }

    .org-note {
        margin: 0.8rem 0 1rem;
        color: #8b90a0;
        font-size: 0.68rem;
        line-height: 1.45;
    }

    .messenger-row {
        display: flex;
        width: 100%;
        min-width: 0;
        align-items: flex-start;
        gap: 0.7rem;
        margin-bottom: 0.9rem;
    }

    .messenger-row-user {
        justify-content: flex-end;
    }

    .messenger-bubble {
        box-sizing: border-box;
        width: fit-content;
        min-width: 0;
        max-width: min(78%, 760px);
        overflow: hidden;
        padding: 0.9rem 1.1rem;
        border-radius: 17px;
        font-size: 0.96rem;
        line-height: 1.78;
        overflow-wrap: anywhere;
        word-break: normal;
    }

    .messenger-bubble-user {
        border-top-right-radius: 5px;
        background: #fee500;
        color: #171717;
    }

    .messenger-bubble-employee {
        border: 1px solid rgba(139, 153, 255, 0.22);
        border-top-left-radius: 5px;
        background: linear-gradient(
            135deg,
            rgba(35, 39, 56, 0.98),
            rgba(26, 29, 40, 0.98)
        );
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.14);
    }

    .messenger-bubble h1,
    .messenger-bubble h2,
    .messenger-bubble h3,
    .messenger-bubble h4,
    .messenger-bubble h5,
    .messenger-bubble h6 {
        margin: 1rem 0 0.42rem;
        font-size: 1rem;
        font-weight: 850;
        line-height: 1.5;
    }

    .messenger-bubble h2 {
        padding: 0.35rem 0 0.28rem;
        border-bottom: 1px solid rgba(139, 153, 255, 0.26);
        color: #d8ddff;
        font-size: 1.05rem;
    }

    .messenger-bubble h3 {
        color: #d8ddff;
        font-size: 0.98rem;
    }

    .messenger-bubble h1:first-child,
    .messenger-bubble h2:first-child,
    .messenger-bubble h3:first-child,
    .messenger-bubble h4:first-child,
    .messenger-bubble h5:first-child,
    .messenger-bubble h6:first-child,
    .messenger-bubble p:first-child,
    .messenger-bubble ul:first-child,
    .messenger-bubble ol:first-child {
        margin-top: 0;
    }

    .messenger-bubble p,
    .messenger-bubble ul,
    .messenger-bubble ol,
    .messenger-bubble blockquote {
        margin: 0.38rem 0 0.9rem;
    }

    .messenger-bubble ul,
    .messenger-bubble ol {
        padding-left: 1.4rem;
    }

    .messenger-bubble li {
        margin: 0.28rem 0;
    }

    .messenger-bubble li.chat-detail-item {
        margin: 0.5rem 0;
        padding: 0.52rem 0.68rem;
        border: 1px solid transparent;
        border-radius: 8px;
        line-height: 1.68;
        list-style: none;
    }

    .messenger-bubble .chat-detail-label {
        display: inline-block;
        min-width: 4.8rem;
        margin-right: 0.35rem;
        border-radius: 5px;
        font-size: 0.78rem;
        font-weight: 800;
        line-height: 1.45;
        text-align: center;
    }

    .messenger-bubble .chat-choice-card {
        margin: 1rem 0;
        padding: 0.82rem 0.9rem 0.72rem;
        border: 1px solid rgba(115, 130, 255, 0.3);
        border-radius: 12px;
        background: linear-gradient(
            135deg,
            rgba(68, 78, 160, 0.24),
            rgba(34, 39, 72, 0.5)
        );
    }

    .messenger-bubble .chat-choice-card h3 {
        margin: 0 0 0.64rem;
        padding: 0 0 0.46rem;
        border-bottom: 1px solid rgba(154, 166, 255, 0.3);
        color: #edf0ff;
        font-size: 1rem;
    }

    .messenger-bubble .chat-choice-details > ul {
        margin: 0;
        padding: 0;
    }

    .messenger-bubble .chat-detail-item-difference {
        border-color: rgba(75, 174, 255, 0.26);
        background: rgba(35, 124, 197, 0.14);
        color: #e5f4ff;
    }

    .messenger-bubble .chat-detail-label-difference {
        background: rgba(50, 154, 231, 0.3);
        color: #d9f2ff;
    }

    .messenger-bubble .chat-detail-item-recommendation {
        border-color: rgba(79, 205, 145, 0.28);
        background: rgba(38, 139, 91, 0.16);
        color: #e2ffef;
    }

    .messenger-bubble .chat-detail-label-recommendation {
        background: rgba(45, 172, 108, 0.34);
        color: #e2fff0;
    }

    .messenger-bubble .chat-detail-item-confirmed {
        border-color: rgba(92, 197, 171, 0.28);
        background: rgba(38, 124, 108, 0.15);
    }

    .messenger-bubble .chat-detail-label-confirmed {
        background: rgba(51, 154, 133, 0.34);
        color: #ddfff6;
    }

    .messenger-bubble .chat-detail-item-proposal {
        border-color: rgba(176, 137, 255, 0.3);
        background: rgba(112, 76, 183, 0.16);
    }

    .messenger-bubble .chat-detail-label-proposal {
        background: rgba(133, 89, 211, 0.36);
        color: #f1e8ff;
    }

    .messenger-bubble .chat-detail-item-unknown {
        border-color: rgba(238, 173, 72, 0.32);
        background: rgba(155, 104, 27, 0.17);
        color: #fff1d7;
    }

    .messenger-bubble .chat-detail-label-unknown {
        background: rgba(204, 137, 35, 0.4);
        color: #fff5df;
    }

    .messenger-bubble .chat-caution {
        display: block;
        margin-top: 0.4rem;
        padding-top: 0.4rem;
        border-top: 1px dashed rgba(246, 187, 91, 0.38);
        color: #ffd58b;
        font-size: 0.9em;
        font-weight: 700;
    }

    .employee-assignment-heading {
        margin: 1rem 0 0.45rem !important;
        padding: 0 !important;
        list-style: none !important;
    }

    .employee-assignment-heading:first-child {
        margin-top: 0.35rem !important;
    }

    .employee-assignment-badge {
        display: inline-flex;
        max-width: 100%;
        align-items: center;
        overflow: hidden;
        border: 1px solid rgba(142, 156, 255, 0.42);
        border-radius: 9px;
        background: linear-gradient(135deg, #5865f2, #7654d6);
        box-shadow: 0 4px 14px rgba(58, 69, 180, 0.18);
        color: #ffffff;
        line-height: 1.25;
        vertical-align: middle;
    }

    .employee-assignment-name,
    .employee-assignment-role {
        display: block;
        overflow: hidden;
        padding: 0.38rem 0.55rem;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .employee-assignment-name {
        font-size: 0.84rem;
        font-weight: 850;
    }

    .employee-assignment-role {
        border-left: 1px solid rgba(255, 255, 255, 0.24);
        background: rgba(10, 15, 45, 0.18);
        color: #e2e6ff;
        font-size: 0.72rem;
        font-weight: 700;
    }

    .employee-assignment-heading > ul,
    .employee-assignment-heading > p + ul {
        margin: 0.55rem 0 0.2rem 0.25rem !important;
        padding-left: 1.25rem !important;
        border-left: 2px solid rgba(88, 101, 242, 0.28);
    }

    .manager-context-body {
        min-width: 0;
        overflow-wrap: anywhere;
        line-height: 1.62;
    }

    .manager-context-body ul,
    .manager-context-body ol {
        padding-left: 1.35rem;
    }

    .manager-context-body > :first-child {
        margin-top: 0;
    }

    .manager-context-body > :last-child {
        margin-bottom: 0;
    }

    .messenger-bubble p:last-child,
    .messenger-bubble ul:last-child,
    .messenger-bubble ol:last-child,
    .messenger-bubble blockquote:last-child {
        margin-bottom: 0;
    }

    .messenger-bubble pre,
    .messenger-bubble table {
        display: block;
        width: 100%;
        max-width: 100%;
        overflow-x: auto;
    }

    .messenger-bubble pre {
        box-sizing: border-box;
        padding: 0.65rem;
        border-radius: 8px;
        background: rgba(128, 128, 128, 0.12);
        white-space: pre-wrap;
    }

    .messenger-bubble table {
        border-collapse: collapse;
        font-size: 0.82rem;
    }

    .messenger-bubble th,
    .messenger-bubble td {
        padding: 0.35rem 0.45rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
        text-align: left;
    }

    .messenger-bubble-user a,
    .messenger-bubble-user code {
        color: #171717;
    }

    .messenger-avatar {
        display: grid;
        place-items: center;
        flex: 0 0 56px;
        width: 56px;
        height: 56px;
        overflow: hidden;
        border: 2px solid rgba(128, 128, 128, 0.18);
        border-radius: 50%;
        background: rgba(128, 128, 128, 0.12);
        font-size: 1.45rem;
    }

    .messenger-avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 28%;
    }

    .messenger-employee-name {
        margin-bottom: 0.28rem;
        color: #5865f2;
        font-size: 0.72rem;
        font-weight: 750;
    }

    .office-dashboard-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin: 0.1rem 0 0.5rem;
        padding: 0.68rem 0.85rem;
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(88, 101, 242, 0.10), rgba(49, 183, 174, 0.06));
    }

    .office-eyebrow {
        color: #7f8798;
        font-family: monospace;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.12em;
    }

    .office-project-name {
        margin-top: 0.18rem;
        font-size: 1.08rem;
        font-weight: 800;
    }

    .office-live-status {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        white-space: nowrap;
        color: #299866;
        font-size: 0.78rem;
        font-weight: 700;
    }

    .office-live-status span {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #2fb879;
        box-shadow: 0 0 0 5px rgba(47, 184, 121, 0.13);
        animation: office-pulse 1.8s ease-in-out infinite;
    }

    .game-stat-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        margin-bottom: 0.5rem;
        overflow: hidden;
        border: 1px solid rgba(128, 128, 128, 0.16);
        border-radius: 11px;
        background: var(--secondary-background-color);
    }

    .game-stat-strip > div {
        display: flex;
        align-items: baseline;
        gap: 0.42rem;
        padding: 0.5rem 0.7rem;
        border-right: 1px solid rgba(128, 128, 128, 0.13);
    }

    .game-stat-strip > div:last-child {
        border-right: 0;
    }

    .game-stat-strip strong {
        font-family: monospace;
        font-size: 1rem;
    }

    .game-stat-strip span {
        color: #858a99;
        font-size: 0.64rem;
        font-weight: 700;
    }

    .pixel-office-stage {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        min-height: 520px;
        border: 7px solid #201e31;
        border-radius: 14px;
        background-position: center;
        background-repeat: no-repeat;
        background-size: cover;
        box-shadow: 0 20px 48px rgba(20, 22, 34, 0.28);
        image-rendering: auto;
    }

    .pixel-office-stage::after {
        position: absolute;
        inset: 0;
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 12px;
        content: "";
        pointer-events: none;
    }

    .office-handoff-layer {
        position: absolute;
        z-index: 3;
        inset: 0;
        width: 100%;
        height: 100%;
        overflow: visible;
        pointer-events: none;
    }

    .office-handoff-route {
        opacity: 0.34;
    }

    .office-handoff-route.latest {
        opacity: 0.95;
        filter: drop-shadow(0 0 5px rgba(255, 235, 125, 0.8));
    }

    .office-handoff-line {
        fill: none;
        stroke: #ffe77a;
        stroke-width: 3;
        stroke-linecap: round;
        stroke-dasharray: 8 7;
        vector-effect: non-scaling-stroke;
        animation: office-route-flow 0.55s linear infinite;
    }

    .office-handoff-point {
        fill: #fff3a8;
        stroke: #3d3548;
        stroke-width: 2;
        vector-effect: non-scaling-stroke;
    }

    .office-file-packet {
        filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.55));
    }

    .office-file-packet rect {
        fill: #fff8ce;
        stroke: #4e4660;
        stroke-width: 2;
        vector-effect: non-scaling-stroke;
    }

    .office-file-packet path {
        fill: none;
        stroke: #7b6c4d;
        stroke-width: 1.5;
        stroke-linecap: round;
        vector-effect: non-scaling-stroke;
    }

    .office-room-label {
        position: absolute;
        z-index: 2;
        padding: 0.24rem 0.55rem;
        border-left: 4px solid var(--room-color);
        border-radius: 4px;
        background: rgba(16, 18, 28, 0.84);
        color: white;
        font-size: clamp(0.55rem, 1.15vw, 0.78rem);
        font-weight: 800;
        box-shadow: 0 3px 9px rgba(0, 0, 0, 0.25);
    }

    .office-agent {
        position: absolute;
        z-index: 4;
        display: flex;
        width: 138px;
        transform: translate(-50%, -50%);
        flex-direction: column;
        align-items: center;
        text-align: center;
        color: inherit;
        text-decoration: none !important;
        cursor: pointer;
        transition: filter 0.18s ease, transform 0.18s ease;
    }

    .office-agent:hover {
        z-index: 8;
        filter: brightness(1.15);
        transform: translate(-50%, -54%) scale(1.08);
    }

    .office-agent.motion-work {
        animation: office-walk-to-desk 0.9s steps(6, end) infinite;
        animation-delay: var(--motion-delay);
    }

    .office-agent.motion-review {
        animation: office-review-route 1.05s ease-in-out infinite;
        animation-delay: var(--motion-delay);
    }

    .office-agent.motion-rework {
        animation: office-rework-route 0.62s steps(5, end) infinite;
        animation-delay: var(--motion-delay);
    }

    .office-agent.motion-coordinate {
        animation: office-coordinate-route 1.15s ease-in-out infinite;
        animation-delay: var(--motion-delay);
    }

    .office-agent.motion-still,
    .office-agent.motion-complete {
        animation: none;
    }

    .office-agent.handoff-sender .office-status-bubble,
    .office-agent.handoff-receiver .office-status-bubble {
        border-color: #ffe77a;
        box-shadow: 0 0 0 2px rgba(255, 231, 122, 0.22),
                    0 0 14px rgba(255, 231, 122, 0.52);
    }

    .office-agent.handoff-receiver .office-sprite {
        filter: drop-shadow(0 0 10px rgba(255, 231, 122, 0.95));
    }

    .office-agent:focus-visible {
        outline: 3px solid white;
        outline-offset: 5px;
    }

    .office-character {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: clamp(82px, 8.2vw, 130px);
        height: clamp(108px, 10.8vw, 165px);
        justify-content: flex-end;
        filter: drop-shadow(0 7px 5px rgba(0, 0, 0, 0.42));
        transform-origin: bottom center;
    }

    .office-sprite {
        position: relative;
        z-index: 2;
        display: block;
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center bottom;
        image-rendering: auto;
    }

    .office-character-shadow {
        position: absolute;
        z-index: 1;
        bottom: 3px;
        left: 50%;
        width: 58%;
        height: 12px;
        border-radius: 50%;
        background: rgba(12, 11, 20, 0.34);
        filter: blur(2px);
        transform: translateX(-50%);
    }

    .office-sprite-fallback {
        display: grid;
        place-items: center;
        width: 78px;
        height: 78px;
        overflow: hidden;
        border: 3px solid white;
        border-radius: 18px;
        background: #e9eaf1;
    }

    .office-sprite-fallback img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .office-avatar {
        position: relative;
        z-index: 2;
        display: grid;
        place-items: center;
        width: clamp(35px, 4.2vw, 50px);
        height: clamp(35px, 4.2vw, 50px);
        overflow: hidden;
        border: 3px solid white;
        border-radius: 50%;
        background: #e9eaf1;
        font-size: 1.2rem;
        box-shadow: 0 0 0 3px var(--agent-color);
    }

    .office-avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 25%;
        image-rendering: auto;
    }

    .office-character-body {
        width: clamp(22px, 2.6vw, 31px);
        height: clamp(20px, 2.4vw, 29px);
        margin-top: -5px;
        border: 3px solid rgba(255, 255, 255, 0.9);
        border-radius: 7px 7px 3px 3px;
        background: var(--agent-color);
    }

    .office-status-bubble {
        max-width: 142px;
        margin-bottom: 2px;
        padding: 0.25rem 0.5rem;
        border: 1px solid rgba(255, 255, 255, 0.55);
        border-radius: 8px;
        background: rgba(20, 22, 33, 0.88);
        color: white;
        font-size: clamp(0.53rem, 0.7vw, 0.68rem);
        font-weight: 700;
        line-height: 1.15;
        white-space: nowrap;
    }

    .office-agent-name,
    .office-agent-title {
        max-width: 138px;
        overflow: hidden;
        color: white;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .office-agent-name {
        margin-top: -2px;
        padding: 0.08rem 0.38rem;
        border-radius: 5px;
        background: rgba(18, 17, 29, 0.72);
        font-size: clamp(0.62rem, 0.8vw, 0.78rem);
        font-weight: 850;
    }

    .office-agent-title {
        margin-top: 1px;
        font-size: clamp(0.48rem, 0.62vw, 0.6rem);
        opacity: 0.84;
    }

    .state-ready .office-character,
    .state-waiting .office-character {
        animation: office-idle 2.2s ease-in-out infinite;
    }

    .state-working .office-character {
        animation: office-working 0.55s steps(2, end) infinite;
    }

    .state-reviewing .office-character {
        animation: office-review 1.3s ease-in-out infinite;
    }

    .state-complete .office-sprite {
        filter: drop-shadow(0 0 10px rgba(53, 199, 123, 0.9));
    }

    .state-error .office-sprite {
        filter: drop-shadow(0 0 11px rgba(255, 94, 105, 0.95));
        animation: office-error 0.45s ease-in-out 3;
    }

    .state-inactive {
        filter: grayscale(1);
        opacity: 0.58;
    }

    .office-activity-bar {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        margin-top: 0.75rem;
        padding: 0.7rem 0.9rem;
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 12px;
        background: var(--secondary-background-color);
        font-size: 0.76rem;
        line-height: 1.4;
    }

    .office-activity-bar span:not(.office-activity-icon) {
        color: #7f8798;
    }

    .office-activity-copy {
        min-width: 0;
    }

    .office-handoff-summary {
        width: fit-content;
        margin-top: 0.38rem;
        padding: 0.18rem 0.48rem;
        border-radius: 999px;
        background: rgba(88, 101, 242, 0.11);
        color: #5865f2;
        font-size: 0.68rem;
        font-weight: 750;
    }

    .office-activity-icon {
        display: grid;
        flex: 0 0 28px;
        place-items: center;
        width: 28px;
        height: 28px;
        border-radius: 8px;
        background: #5865f2;
        color: white;
    }

    .employee-room-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.72rem;
    }

    .employee-room-card {
        display: block;
        min-width: 0;
        overflow: hidden;
        border: 1px solid color-mix(in srgb, var(--room-accent) 48%, rgba(255, 255, 255, 0.18));
        border-radius: 16px;
        background: #161824;
        color: white !important;
        text-decoration: none !important;
        box-shadow: 0 15px 34px rgba(9, 10, 17, 0.23);
        transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
    }

    .employee-room-card:hover {
        border-color: var(--room-accent);
        box-shadow: 0 20px 42px rgba(9, 10, 17, 0.32),
                    0 0 0 2px color-mix(in srgb, var(--room-accent) 28%, transparent);
        transform: translateY(-4px);
    }

    .employee-room-scene {
        position: relative;
        display: block;
        height: 190px;
        aspect-ratio: 16 / 9;
        min-height: 0;
        overflow: hidden;
        isolation: isolate;
        background-position: center;
        background-repeat: no-repeat;
        background-size: cover;
        color: white !important;
        text-decoration: none !important;
    }

    .employee-room-scene::after {
        position: absolute;
        z-index: 1;
        inset: 0;
        border: 1px solid rgba(255, 255, 255, 0.12);
        content: "";
        pointer-events: none;
    }

    .employee-room-shade {
        position: absolute;
        z-index: 1;
        inset: 0;
        background:
            linear-gradient(180deg, rgba(8, 10, 18, 0.48) 0%, transparent 34%),
            linear-gradient(90deg, rgba(8, 10, 18, 0.18), transparent 52%, rgba(8, 10, 18, 0.2));
        pointer-events: none;
    }

    .employee-room-heading {
        position: absolute;
        z-index: 4;
        top: 0.6rem;
        left: 0.65rem;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        max-width: 54%;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.75);
    }

    .employee-room-heading span {
        font-size: clamp(0.78rem, 1.15vw, 1.02rem);
        font-weight: 900;
    }

    .employee-room-heading em {
        margin-top: 0.12rem;
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.63rem;
        font-style: normal;
        font-weight: 700;
    }

    .employee-room-status {
        position: absolute;
        z-index: 5;
        top: 0.58rem;
        right: 0.58rem;
        max-width: 42%;
        padding: 0.3rem 0.55rem;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 999px;
        background: rgba(15, 17, 27, 0.82);
        font-size: 0.64rem;
        font-weight: 800;
        text-overflow: ellipsis;
        white-space: nowrap;
        backdrop-filter: blur(6px);
    }

    .employee-room-character {
        position: absolute;
        z-index: 3;
        right: 4%;
        bottom: 0;
        display: flex;
        width: 48%;
        height: 82%;
        align-items: flex-end;
        justify-content: center;
        transform-origin: center bottom;
        animation: room-character-idle 3.2s ease-in-out infinite;
        animation-delay: var(--room-delay);
        pointer-events: none;
    }

    .employee-room-character > img {
        position: relative;
        z-index: 2;
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center bottom;
        filter: drop-shadow(0 9px 6px rgba(0, 0, 0, 0.48));
    }

    .employee-room-character > .employee-frame-sprite {
        position: relative;
        z-index: 2;
        display: block;
        height: 100%;
        aspect-ratio: 3 / 4;
        overflow: visible;
        filter: drop-shadow(0 9px 6px rgba(0, 0, 0, 0.48));
        image-rendering: auto;
    }

    .employee-animation-frame {
        position: absolute;
        display: block;
        overflow: hidden;
        opacity: 0;
        animation-duration: var(--frame-duration, 1.2s);
        animation-timing-function: steps(1, end);
        animation-iteration-count: var(--frame-iterations, infinite);
        animation-fill-mode: forwards;
    }

    .employee-animation-frame > img {
        position: absolute;
        width: auto;
        max-width: none;
        image-rendering: auto;
    }

    .employee-animation-frame.frame-index-1 {
        opacity: 1;
        animation-name: employee-show-frame-1;
    }

    .employee-animation-frame.frame-index-2 {
        animation-name: employee-show-frame-2;
    }

    .employee-animation-frame.frame-index-3 {
        animation-name: employee-show-frame-3;
    }

    .employee-animation-frame.frame-index-4 {
        animation-name: employee-show-frame-4;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-1 {
        animation-name: employee-show-frame-8-1;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-2 {
        animation-name: employee-show-frame-8-2;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-3 {
        animation-name: employee-show-frame-8-3;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-4 {
        animation-name: employee-show-frame-8-4;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-5 {
        animation-name: employee-show-frame-8-5;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-6 {
        animation-name: employee-show-frame-8-6;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-7 {
        animation-name: employee-show-frame-8-7;
    }

    .employee-frame-sprite.frames-8 .employee-animation-frame.frame-index-8 {
        animation-name: employee-show-frame-8-8;
    }

    .employee-room-character.has-frame-animation {
        animation: none !important;
    }

    .employee-room-character.action-idle > .employee-frame-sprite {
        --frame-duration: 3.2s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-thinking > .employee-frame-sprite {
        --frame-duration: 1.8s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-working > .employee-frame-sprite {
        --frame-duration: 1.05s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-talking > .employee-frame-sprite {
        --frame-duration: 1.25s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-handoff > .employee-frame-sprite {
        --frame-duration: 1.15s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-handoff > .employee-frame-sprite .employee-animation-frame {
        animation-iteration-count: infinite !important;
        animation-fill-mode: none;
    }

    .employee-room-character.action-complete > .employee-frame-sprite {
        --frame-duration: 1.4s;
        --frame-iterations: infinite;
    }

    .employee-room-character.action-complete > .employee-frame-sprite .employee-animation-frame {
        animation-iteration-count: infinite !important;
        animation-fill-mode: none;
    }

    .employee-room-character.action-rework > .employee-frame-sprite {
        --frame-duration: 1.1s;
        --frame-iterations: infinite;
    }

    .employee-room-character > i {
        position: absolute;
        z-index: 1;
        right: 16%;
        bottom: 4%;
        left: 16%;
        height: 10%;
        border-radius: 50%;
        background: rgba(4, 5, 10, 0.38);
        filter: blur(4px);
    }

    .employee-room-card.state-working .employee-room-character {
        animation: room-character-working 0.95s ease-in-out infinite;
    }

    .employee-room-card.state-reviewing .employee-room-character {
        animation: room-character-review 1.7s ease-in-out infinite;
    }

    .employee-room-card.state-complete .employee-room-character,
    .employee-room-card.state-inactive .employee-room-character {
        animation: none;
    }

    .employee-room-card.state-complete .employee-room-character > img {
        filter: drop-shadow(0 0 12px rgba(64, 220, 151, 0.86));
    }

    .employee-room-card.state-error .employee-room-character {
        animation: room-character-error 0.42s ease-in-out 3;
    }

    .employee-room-card.state-inactive {
        filter: grayscale(0.9);
        opacity: 0.64;
    }

    .employee-room-working-light {
        position: absolute;
        z-index: 2;
        right: 4%;
        bottom: 3%;
        width: 46%;
        height: 70%;
        border-radius: 50%;
        background: radial-gradient(circle, color-mix(in srgb, var(--room-accent) 32%, transparent), transparent 68%);
        opacity: 0;
        pointer-events: none;
    }

    .state-working .employee-room-working-light,
    .state-reviewing .employee-room-working-light {
        opacity: 1;
        animation: room-work-light 1.6s ease-in-out infinite;
    }

    .employee-room-handoff {
        position: absolute;
        z-index: 6;
        bottom: 0.72rem;
        left: 0.8rem;
        padding: 0.28rem 0.55rem;
        border: 1px solid rgba(255, 237, 137, 0.72);
        border-radius: 999px;
        background: rgba(37, 31, 16, 0.88);
        color: #ffed89;
        font-size: 0.62rem;
        font-weight: 850;
        box-shadow: 0 0 14px rgba(255, 231, 122, 0.28);
        animation: room-handoff-badge 1.4s ease-in-out infinite;
    }

    .employee-room-footer {
        position: relative;
        display: grid;
        grid-template-columns: minmax(82px, 0.62fr) minmax(0, 1.38fr) auto;
        gap: 0.45rem;
        align-items: center;
        min-height: 62px;
        padding: 0.48rem 0.62rem;
        border-top: 3px solid var(--room-accent);
        background: linear-gradient(110deg, rgba(25, 27, 40, 0.99), rgba(18, 20, 31, 0.99));
    }

    .employee-room-footer strong,
    .employee-room-footer span {
        display: block;
    }

    .employee-room-footer strong {
        font-size: 0.94rem;
    }

    .employee-room-footer span,
    .employee-room-footer p {
        color: rgba(255, 255, 255, 0.68);
        font-size: 0.66rem;
        line-height: 1.42;
    }

    .employee-room-footer p {
        display: -webkit-box;
        margin: 0;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
    }

    .employee-room-actions {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        align-items: stretch;
    }

    .employee-room-open-button,
    .employee-room-data-button {
        display: block;
        padding: 0.23rem 0.42rem;
        border-radius: 6px;
        text-align: center;
        text-decoration: none !important;
        white-space: nowrap;
    }

    .employee-room-open-button {
        color: var(--room-accent);
        font-size: 0.65rem;
        font-weight: 800;
    }

    .employee-room-data-button {
        border: 1px solid rgba(255, 231, 122, 0.62);
        background: rgba(255, 231, 122, 0.12);
        color: #ffeb81 !important;
        font-size: 0.62rem;
        font-weight: 850;
    }

    .employee-room-data-button:hover {
        background: rgba(255, 231, 122, 0.22);
    }

    .meeting-room-card {
        position: relative;
        display: block;
        height: 126px;
        margin-top: 0.95rem;
        overflow: hidden;
        border: 1px solid rgba(126, 187, 162, 0.45);
        border-radius: 16px;
        color: white !important;
        text-decoration: none !important;
        box-shadow: 0 16px 36px rgba(9, 10, 17, 0.24);
        transition: transform 0.22s ease, border-color 0.22s ease;
    }

    .meeting-room-card:hover {
        border-color: #88d5b5;
        transform: translateY(-3px);
    }

    .meeting-room-background,
    .meeting-room-overlay {
        position: absolute;
        inset: 0;
    }

    .meeting-room-background {
        background-position: center;
        background-size: cover;
        transition: transform 0.45s ease;
    }

    .meeting-room-card:hover .meeting-room-background {
        transform: scale(1.025);
    }

    .meeting-room-overlay {
        background: linear-gradient(90deg, rgba(13, 16, 24, 0.88), rgba(13, 16, 24, 0.34) 58%, rgba(13, 16, 24, 0.64));
    }

    .meeting-room-copy {
        position: absolute;
        z-index: 2;
        top: 50%;
        left: 1rem;
        max-width: 55%;
        transform: translateY(-50%);
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.72);
    }

    .meeting-room-copy span,
    .meeting-room-copy strong,
    .meeting-room-copy p,
    .meeting-room-copy b {
        display: block;
    }

    .meeting-room-copy span {
        color: #9fd9c2;
        font-family: monospace;
        font-size: 0.66rem;
        font-weight: 850;
        letter-spacing: 0.14em;
    }

    .meeting-room-copy strong {
        margin-top: 0.3rem;
        font-size: 1.18rem;
    }

    .meeting-room-copy p {
        margin: 0.2rem 0 0.34rem;
        color: rgba(255, 255, 255, 0.78);
        font-size: 0.75rem;
    }

    .meeting-room-copy b {
        color: #8ee2bd;
        font-size: 0.72rem;
    }

    .meeting-room-participants {
        position: absolute;
        z-index: 3;
        right: 1.05rem;
        bottom: 0.9rem;
        display: flex;
        align-items: flex-end;
    }

    .meeting-room-participants i {
        display: grid;
        width: 40px;
        height: 48px;
        margin-left: -10px;
        overflow: hidden;
        place-items: end center;
        border: 2px solid rgba(255, 255, 255, 0.82);
        border-radius: 50% 50% 12px 12px;
        background: rgba(25, 27, 38, 0.86);
        box-shadow: 0 5px 12px rgba(0, 0, 0, 0.28);
    }

    .meeting-room-participants img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center bottom;
    }

    .meeting-room-participants span {
        align-self: center;
        font-size: 0.7rem;
    }

    .meeting-room-card.meeting-active {
        box-shadow: 0 0 0 2px rgba(91, 222, 163, 0.2), 0 0 24px rgba(91, 222, 163, 0.24);
    }

    .meeting-dialog-hero {
        position: relative;
        min-height: 310px;
        margin-bottom: 0.8rem;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 14px;
        background-position: center;
        background-size: cover;
    }

    .meeting-dialog-shade {
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, rgba(14, 17, 25, 0.84), rgba(14, 17, 25, 0.12) 62%, rgba(14, 17, 25, 0.42));
    }

    .meeting-dialog-title {
        position: absolute;
        z-index: 2;
        top: 1.2rem;
        left: 1.25rem;
        max-width: 58%;
        color: white;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.75);
    }

    .meeting-dialog-title span,
    .meeting-dialog-title strong,
    .meeting-dialog-title p {
        display: block;
    }

    .meeting-dialog-title span {
        color: #9fe2c6;
        font-family: monospace;
        font-size: 0.67rem;
        font-weight: 850;
        letter-spacing: 0.12em;
    }

    .meeting-dialog-title strong {
        margin-top: 0.3rem;
        font-size: 1.45rem;
    }

    .meeting-dialog-title p {
        color: rgba(255, 255, 255, 0.76);
        font-size: 0.72rem;
    }

    .meeting-dialog-participants {
        position: absolute;
        z-index: 3;
        right: 1rem;
        bottom: 0.8rem;
        left: 1rem;
        display: flex;
        justify-content: flex-end;
        gap: 0.35rem;
    }

    .meeting-dialog-participants > div {
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .meeting-dialog-participants i {
        display: flex;
        width: 52px;
        height: 66px;
        overflow: hidden;
        align-items: flex-end;
        justify-content: center;
        border: 2px solid rgba(255, 255, 255, 0.82);
        border-radius: 50% 50% 12px 12px;
        background: rgba(21, 23, 33, 0.85);
    }

    .meeting-dialog-participants img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        object-position: center bottom;
    }

    .meeting-dialog-participants span {
        margin-top: 0.18rem;
        color: white;
        font-size: 0.58rem;
        font-weight: 800;
        text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
    }

    .handoff-dialog-route {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 110px minmax(0, 1fr);
        gap: 0.8rem;
        align-items: center;
        padding: 1rem;
        border: 1px solid rgba(255, 231, 122, 0.26);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(88, 101, 242, 0.1), rgba(255, 231, 122, 0.07));
    }

    .handoff-dialog-person {
        display: flex;
        min-width: 0;
        flex-direction: column;
        align-items: center;
        text-align: center;
    }

    .handoff-dialog-person i {
        display: grid;
        width: 72px;
        height: 72px;
        overflow: hidden;
        place-items: center;
        border: 3px solid rgba(255, 255, 255, 0.82);
        border-radius: 50%;
        background: var(--secondary-background-color);
        font-size: 1.6rem;
        box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
    }

    .handoff-dialog-person i img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 24%;
    }

    .handoff-dialog-person strong,
    .handoff-dialog-person span {
        display: block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .handoff-dialog-person strong {
        margin-top: 0.42rem;
        font-size: 0.86rem;
    }

    .handoff-dialog-person span {
        color: #868c9a;
        font-size: 0.64rem;
    }

    .handoff-dialog-arrow {
        text-align: center;
    }

    .handoff-dialog-arrow b,
    .handoff-dialog-arrow span {
        display: block;
    }

    .handoff-dialog-arrow b {
        color: #9a8d55;
        font-size: 0.64rem;
    }

    .handoff-dialog-arrow span {
        color: #f0cc48;
        font-size: 2rem;
        line-height: 1;
        animation: handoff-arrow-move 1.2s ease-in-out infinite;
    }

    .handoff-dialog-project {
        margin: 0.55rem 0 0.85rem;
        color: #858b99;
        font-size: 0.7rem;
        text-align: center;
    }

    .visual-novel-scene {
        background-position: center !important;
        background-size: cover !important;
    }

    .visual-novel-scene::before {
        position: absolute;
        z-index: 1;
        inset: 0;
        background: linear-gradient(90deg, rgba(20, 24, 39, 0.36), rgba(20, 24, 39, 0.78));
        content: "";
    }

    .game-live-panel {
        min-height: 100%;
        margin-top: 0.1rem;
        padding: 0.8rem;
        border: 1px solid rgba(128, 128, 128, 0.17);
        border-radius: 14px;
        background: linear-gradient(180deg, rgba(32, 30, 49, 0.98), rgba(23, 22, 36, 0.98));
        color: white;
        box-shadow: 0 15px 36px rgba(20, 18, 31, 0.2);
    }

    .game-panel-kicker,
    .game-panel-section-title {
        color: #9793aa;
        font-family: monospace;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.13em;
    }

    .game-focus-card {
        display: grid;
        grid-template-columns: 82px minmax(0, 1fr);
        gap: 0.65rem;
        align-items: center;
        margin: 0.55rem 0 0.75rem;
        padding: 0.55rem;
        border: 1px solid rgba(255, 227, 110, 0.34);
        border-radius: 11px;
        background: rgba(255, 255, 255, 0.055);
        color: white !important;
        text-decoration: none !important;
    }

    .game-focus-card:hover {
        border-color: #ffe36e;
        background: rgba(255, 227, 110, 0.09);
    }

    .game-focus-portrait {
        display: flex;
        align-items: flex-end;
        justify-content: center;
        height: 105px;
        overflow: hidden;
        border-radius: 9px;
        background:
            radial-gradient(circle at 50% 25%, rgba(255, 227, 110, 0.15), transparent 55%),
            rgba(255, 255, 255, 0.04);
    }

    .game-focus-portrait img {
        width: 90px;
        height: 120px;
        object-fit: contain;
        object-position: center bottom;
        image-rendering: auto;
    }

    .game-focus-copy strong,
    .game-focus-copy span,
    .game-focus-copy em {
        display: block;
    }

    .game-focus-copy strong {
        font-size: 1.05rem;
    }

    .game-focus-copy span {
        margin-top: 0.15rem;
        color: #aaa6b8;
        font-size: 0.67rem;
    }

    .game-focus-copy em {
        margin-top: 0.55rem;
        color: #61d7a5;
        font-size: 0.67rem;
        font-style: normal;
        font-weight: 750;
    }

    .game-focus-copy i,
    .game-team-state i {
        display: inline-block;
        width: 7px;
        height: 7px;
        margin-right: 0.35rem;
        border-radius: 50%;
        background: currentColor;
        box-shadow: 0 0 7px currentColor;
    }

    .game-progress-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #aaa6b8;
        font-size: 0.67rem;
    }

    .game-progress-head strong {
        color: #ffe36e;
        font-family: monospace;
        font-size: 0.85rem;
    }

    .game-progress-track {
        height: 7px;
        margin: 0.35rem 0 0.9rem;
        overflow: hidden;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.09);
    }

    .game-progress-track span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, #ffe36e, #4ed6a5);
        box-shadow: 0 0 10px rgba(78, 214, 165, 0.45);
        transition: width 0.5s ease;
    }

    .game-team-list {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        margin-top: 0.48rem;
    }

    .game-team-card {
        display: grid;
        grid-template-columns: 38px minmax(0, 1fr) auto;
        gap: 0.48rem;
        align-items: center;
        min-height: 48px;
        padding: 0.28rem 0.38rem;
        border: 1px solid transparent;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.04);
        color: white !important;
        text-decoration: none !important;
    }

    .game-team-card:hover {
        border-color: rgba(255, 227, 110, 0.42);
        background: rgba(255, 255, 255, 0.075);
    }

    .game-team-avatar {
        display: flex;
        align-items: flex-end;
        justify-content: center;
        width: 38px;
        height: 42px;
        overflow: hidden;
        border-radius: 7px;
        background: rgba(255, 255, 255, 0.06);
    }

    .game-team-avatar img {
        width: 38px;
        height: 48px;
        object-fit: contain;
        object-position: center bottom;
        image-rendering: auto;
    }

    .game-team-copy strong,
    .game-team-copy span {
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .game-team-copy strong {
        font-size: 0.72rem;
    }

    .game-team-copy span {
        margin-top: 0.08rem;
        color: #918da3;
        font-size: 0.55rem;
    }

    .game-team-state {
        color: #61d7a5;
        font-size: 0.53rem;
        font-weight: 700;
        white-space: nowrap;
    }

    .game-team-card.state-error .game-team-state {
        color: #ff747e;
    }

    .game-team-card.state-waiting .game-team-state,
    .game-team-card.state-ready .game-team-state {
        color: #aaa6b8;
    }

    .game-panel-tip {
        margin-top: 0.65rem;
        padding: 0.52rem;
        border-radius: 8px;
        background: rgba(88, 101, 242, 0.11);
        color: #9d99ad;
        font-size: 0.56rem;
        line-height: 1.45;
    }

    .agent-console-header {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        gap: 0.8rem;
        align-items: center;
        padding: 0.7rem 0.95rem;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-bottom: 0;
        border-radius: 14px 14px 0 0;
        background: #151724;
        color: white;
    }

    .agent-console-header span {
        color: #aab4ff;
        font-family: monospace;
        font-size: 0.64rem;
        font-weight: 850;
        letter-spacing: 0.12em;
    }

    .agent-console-header strong {
        min-width: 0;
        overflow: hidden;
        font-size: 0.82rem;
        text-align: center;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .agent-console-header em {
        padding: 0.23rem 0.55rem;
        border-radius: 999px;
        background: rgba(53, 199, 123, 0.14);
        color: #61d7a5;
        font-size: 0.65rem;
        font-style: normal;
        font-weight: 800;
    }

    .visual-novel-scene {
        position: relative;
        display: grid;
        grid-template-columns: minmax(190px, 0.42fr) 0.58fr;
        gap: 1.3rem;
        min-height: 310px;
        overflow: hidden;
        padding: 1.5rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 0 0 5px 5px;
        background:
            radial-gradient(circle at 22% 30%, rgba(88, 101, 242, 0.2), transparent 35%),
            linear-gradient(135deg, #1c2031, #303853 55%, #242839);
        color: white;
    }

    .visual-novel-scene::after {
        position: absolute;
        right: -60px;
        bottom: -90px;
        width: 280px;
        height: 280px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 50%;
        box-shadow: 0 0 0 38px rgba(255, 255, 255, 0.025);
        content: "";
    }

    .visual-novel-profile {
        position: relative;
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-end;
    }

    .visual-novel-portrait {
        display: grid;
        place-items: center;
        width: min(220px, 100%);
        aspect-ratio: 1 / 1;
        overflow: hidden;
        border: 4px solid rgba(255, 255, 255, 0.9);
        border-radius: 18px 18px 5px 5px;
        background: rgba(255, 255, 255, 0.09);
        font-size: 5rem;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.35);
    }

    .visual-novel-portrait img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 24%;
    }

    .visual-novel-portrait img.visual-novel-sprite {
        width: 112%;
        height: 112%;
        object-fit: contain;
        object-position: center bottom;
        image-rendering: auto;
        filter: drop-shadow(0 12px 10px rgba(0, 0, 0, 0.36));
    }

    .visual-novel-department {
        margin-top: 0.65rem;
        font-size: 0.78rem;
        font-weight: 800;
    }

    .visual-novel-role {
        margin-top: 0.1rem;
        color: rgba(255, 255, 255, 0.68);
        font-size: 0.68rem;
    }

    .visual-novel-info {
        position: relative;
        z-index: 2;
        align-self: center;
    }

    .visual-novel-kicker {
        color: #aab4ff;
        font-family: monospace;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.14em;
    }

    .visual-novel-name {
        margin: 0.3rem 0 0.75rem;
        font-size: clamp(2rem, 5vw, 3.8rem);
        font-weight: 900;
        letter-spacing: -0.04em;
    }

    .visual-novel-state {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.35rem 0.65rem;
        border: 1px solid rgba(255, 255, 255, 0.17);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.08);
        font-size: 0.72rem;
        font-weight: 700;
    }

    .visual-novel-state span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #35c77b;
        box-shadow: 0 0 12px rgba(53, 199, 123, 0.9);
    }

    .state-error .visual-novel-state span {
        background: #ff5e69;
    }

    .state-inactive .visual-novel-state span {
        background: #858b99;
    }

    .visual-novel-project {
        max-width: 360px;
        margin-top: 1rem;
        color: rgba(255, 255, 255, 0.68);
        font-size: 0.75rem;
        line-height: 1.5;
    }

    .visual-novel-dialogue {
        position: relative;
        z-index: 5;
        min-height: 135px;
        margin: -4px 0 0.8rem;
        padding: 1.15rem 1.25rem;
        border: 2px solid rgba(88, 101, 242, 0.38);
        border-radius: 5px 5px 18px 18px;
        background: var(--secondary-background-color);
        box-shadow: 0 12px 28px rgba(20, 22, 34, 0.14);
    }

    .visual-novel-speaker {
        display: inline-block;
        margin-bottom: 0.65rem;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        background: #5865f2;
        color: white;
        font-size: 0.72rem;
        font-weight: 850;
    }

    .visual-novel-line {
        overflow-wrap: anywhere;
        font-size: 0.94rem;
        line-height: 1.75;
        white-space: pre-line;
    }

    .direct-chat-banner {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin: 0.75rem 0 1rem;
        padding: 0.7rem 0.9rem;
        border: 1px solid rgba(88, 101, 242, 0.22);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(88, 101, 242, 0.11), rgba(169, 120, 232, 0.06));
    }

    .direct-chat-avatar {
        display: grid;
        flex: 0 0 48px;
        place-items: center;
        width: 48px;
        height: 48px;
        overflow: hidden;
        border: 2px solid white;
        border-radius: 50%;
        background: rgba(128, 128, 128, 0.12);
        box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.45);
    }

    .direct-chat-avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 25%;
    }

    .direct-chat-label {
        color: #7f8798;
        font-size: 0.62rem;
        font-weight: 750;
    }

    .direct-chat-name {
        font-size: 0.94rem;
        font-weight: 850;
        line-height: 1.25;
    }

    .direct-chat-role {
        margin-top: 0.08rem;
        color: #7f8798;
        font-size: 0.68rem;
    }

    @keyframes office-idle {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-4px); }
    }

    @keyframes office-working {
        0% { transform: translateX(-2px); }
        100% { transform: translateX(2px); }
    }

    @keyframes office-review {
        0%, 100% { transform: rotate(-2deg) translateY(0); }
        50% { transform: rotate(2deg) translateY(-3px); }
    }

    @keyframes office-error {
        0%, 100% { transform: translateX(0); }
        50% { transform: translateX(5px); }
    }

    @keyframes office-pulse {
        0%, 100% { transform: scale(0.9); opacity: 0.65; }
        50% { transform: scale(1.1); opacity: 1; }
    }

    @keyframes office-route-flow {
        from { stroke-dashoffset: 15; }
        to { stroke-dashoffset: 0; }
    }

    @keyframes office-walk-to-desk {
        0%, 100% { transform: translate(-50%, -50%); }
        45%, 55% {
            transform: translate(
                calc(-50% + var(--walk-x)),
                calc(-50% + var(--walk-y))
            );
        }
    }

    @keyframes office-review-route {
        0%, 100% { transform: translate(-50%, -50%) rotate(-1deg); }
        50% {
            transform: translate(
                calc(-50% + var(--walk-x)),
                calc(-50% + var(--walk-y))
            ) rotate(2deg);
        }
    }

    @keyframes office-rework-route {
        0%, 100% { transform: translate(-50%, -50%); }
        35% {
            transform: translate(
                calc(-50% + var(--walk-x)),
                calc(-50% + var(--walk-y))
            );
        }
        70% {
            transform: translate(
                calc(-50% - var(--walk-x)),
                calc(-50% - var(--walk-y))
            );
        }
    }

    @keyframes office-coordinate-route {
        0%, 100% { transform: translate(-50%, -50%); }
        50% {
            transform: translate(
                calc(-50% + var(--walk-x)),
                calc(-50% + var(--walk-y))
            );
        }
    }

    @keyframes office-finish-bounce {
        0%, 78%, 100% { transform: translate(-50%, -50%); }
        86% { transform: translate(-50%, calc(-50% - 7px)); }
        92% { transform: translate(-50%, -50%); }
    }

    @keyframes office-receive-ring {
        0%, 100% {
            box-shadow: 0 0 0 3px var(--agent-color),
                        0 0 0 0 rgba(255, 231, 122, 0.55);
        }
        50% {
            box-shadow: 0 0 0 3px var(--agent-color),
                        0 0 0 9px rgba(255, 231, 122, 0);
        }
    }

    @keyframes room-character-idle {
        0%, 100% { transform: translateY(0) scale(1); }
        50% { transform: translateY(-3px) scale(1.006); }
    }

    @keyframes room-character-working {
        0%, 100% { transform: translateY(0) rotate(0); }
        45% { transform: translateY(-3px) rotate(-0.7deg); }
        70% { transform: translateY(-1px) rotate(0.7deg); }
    }

    @keyframes employee-show-frame-1 {
        0%, 24.99% { opacity: 1; }
        25%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-2 {
        0%, 24.99% { opacity: 0; }
        25%, 49.99% { opacity: 1; }
        50%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-3 {
        0%, 49.99% { opacity: 0; }
        50%, 74.99% { opacity: 1; }
        75%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-4 {
        0%, 74.99% { opacity: 0; }
        75%, 100% { opacity: 1; }
    }

    @keyframes employee-show-frame-8-1 {
        0%, 12.49% { opacity: 1; }
        12.5%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-2 {
        0%, 12.49% { opacity: 0; }
        12.5%, 24.99% { opacity: 1; }
        25%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-3 {
        0%, 24.99% { opacity: 0; }
        25%, 37.49% { opacity: 1; }
        37.5%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-4 {
        0%, 37.49% { opacity: 0; }
        37.5%, 49.99% { opacity: 1; }
        50%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-5 {
        0%, 49.99% { opacity: 0; }
        50%, 62.49% { opacity: 1; }
        62.5%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-6 {
        0%, 62.49% { opacity: 0; }
        62.5%, 74.99% { opacity: 1; }
        75%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-7 {
        0%, 74.99% { opacity: 0; }
        75%, 87.49% { opacity: 1; }
        87.5%, 100% { opacity: 0; }
    }

    @keyframes employee-show-frame-8-8 {
        0%, 87.49% { opacity: 0; }
        87.5%, 100% { opacity: 1; }
    }

    @keyframes room-character-review {
        0%, 100% { transform: translateX(0); filter: brightness(1); }
        50% { transform: translateX(-3px); filter: brightness(1.08); }
    }

    @keyframes room-character-error {
        0%, 100% { transform: translateX(0); }
        35% { transform: translateX(-5px); }
        70% { transform: translateX(5px); }
    }

    @keyframes room-work-light {
        0%, 100% { opacity: 0.45; transform: scale(0.94); }
        50% { opacity: 1; transform: scale(1.04); }
    }

    @keyframes room-handoff-badge {
        0%, 100% { box-shadow: 0 0 8px rgba(255, 231, 122, 0.22); }
        50% { box-shadow: 0 0 19px rgba(255, 231, 122, 0.55); }
    }

    @keyframes handoff-arrow-move {
        0%, 100% { transform: translateX(-3px); opacity: 0.68; }
        50% { transform: translateX(4px); opacity: 1; }
    }

    @media (prefers-reduced-motion: reduce) {
        .office-agent,
        .office-character,
        .office-avatar,
        .office-handoff-line,
        .office-live-status span,
        .employee-room-character,
        .employee-frame-sprite,
        .employee-animation-frame,
        .employee-room-working-light,
        .employee-room-handoff,
        .handoff-dialog-arrow span {
            animation: none !important;
        }
    }

    @media (max-width: 1250px) {
        .employee-room-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 700px) {
        .messenger-bubble {
            max-width: calc(100% - 58px);
            padding: 0.62rem 0.75rem;
            font-size: 0.88rem;
        }

        .messenger-avatar {
            flex-basis: 48px;
            width: 48px;
            height: 48px;
        }

        .office-dashboard-header {
            align-items: flex-start;
            flex-direction: column;
        }

        .office-agent {
            width: 86px;
        }

        .office-character {
            width: 72px;
            height: 94px;
        }

        .pixel-office-stage {
            min-height: 390px;
        }

        .office-status-bubble,
        .office-agent-title {
            display: none;
        }

        .game-stat-strip span {
            display: none;
        }

        .employee-room-scene {
            height: 205px;
        }

        .employee-room-grid {
            grid-template-columns: 1fr;
        }

        .employee-room-character {
            right: 2%;
            width: 50%;
        }

        .employee-room-footer {
            grid-template-columns: 1fr auto;
        }

        .employee-room-footer p {
            grid-column: 1 / -1;
            grid-row: 2;
        }

        .meeting-room-card {
            height: 150px;
        }

        .meeting-room-copy {
            max-width: 72%;
        }

        .meeting-room-participants,
        .meeting-dialog-participants {
            display: none;
        }

        .visual-novel-scene {
            grid-template-columns: 1fr;
        }

        .agent-console-header {
            grid-template-columns: 1fr auto;
        }

        .agent-console-header span {
            display: none;
        }

        .visual-novel-portrait {
            width: 150px;
        }

        .visual-novel-info {
            text-align: center;
        }

        .visual-novel-project {
            margin-right: auto;
            margin-left: auto;
        }
    }

    

.task-record-label {
        height: 3.75rem;
        min-height: 3.75rem;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        line-height: 1.45;
        color: inherit;
        opacity: 0.78;
        padding: 0.55rem 0.8rem;
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 0.65rem;
        background: rgba(128, 128, 128, 0.055);
        overflow-wrap: anywhere;
    }
    div[class*="st-key-task_record_row_"] [data-testid="stButton"] button {
        height: 3.75rem !important;
        min-height: 3.75rem !important;
    }
    .task-record-bottom-space {
        height: 0.9rem;
    }
</style>
"""


def apply_global_styles() -> None:
    """YOUFFICE 공통 CSS를 화면에 적용합니다."""

    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)
