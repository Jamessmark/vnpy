/**
 * 修复 dcc.Dropdown 每次打开时搜索框预填入已选合约名称的问题。
 *
 * Dash 默认行为：打开下拉菜单时会把当前选中项的 label 填入搜索框，
 * 以供用户在已选项基础上继续过滤。但这在期货合约搜索场景下体验很差——
 * 用户每次打开都要先手动清空才能搜索新合约。
 *
 * 修复方案：用 MutationObserver 监听 #contract-dropdown 内部的 input 元素，
 * 一旦检测到输入框出现（即下拉菜单刚打开），立即清空其内容并触发 React 的
 * change 事件（Dash 组件基于 React，必须手动触发 nativeInputValueSetter）。
 */
(function () {
    function clearDropdownSearchOnOpen(dropdownEl) {
        const observer = new MutationObserver(function (mutations) {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType !== 1) continue;
                    // 检查是否是下拉菜单容器被插入
                    const isMenu =
                        node.classList.contains("Select-menu-outer") ||
                        node.querySelector(".Select-menu-outer");
                    if (!isMenu) continue;

                    // 找到搜索 input 并清空
                    const input = dropdownEl.querySelector("input[type='text'], input:not([type])");
                    if (!input) continue;

                    // React 控制了 input.value，必须用 nativeInputValueSetter 触发事件
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype,
                        "value"
                    ).set;
                    nativeInputValueSetter.call(input, "");
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
            }
        });

        observer.observe(dropdownEl, { childList: true, subtree: true });
    }

    // 等 DOM 准备好后挂载 observer
    function init() {
        const el = document.getElementById("contract-dropdown");
        if (el) {
            clearDropdownSearchOnOpen(el);
        } else {
            // Dash 可能还没渲染，稍后重试
            setTimeout(init, 500);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
