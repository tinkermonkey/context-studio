# Flow Example

## Non-React Example

Below is a non-react example of the flow graph

[Source](https://g6.antv.antgroup.com/en/examples/scene-case/default#fund-flow)

### Example Code

```javascript
import { Rect as GRect, Text as GText } from '@antv/g';
import {
  Badge,
  CommonEvent,
  ExtensionCategory,
  Graph,
  GraphEvent,
  iconfont,
  Label,
  Rect,
  register,
  treeToGraphData,
} from '@antv/g6';

const style = document.createElement('style');
style.innerHTML = `@import url('${iconfont.css}');`;
document.head.appendChild(style);

const COLORS = {
  B: '#1783FF',
  R: '#F46649',
  Y: '#DB9D0D',
  G: '#60C42D',
  DI: '#A7A7A7',
};
const GREY_COLOR = '#CED4D9';

class TreeNode extends Rect {
  get data() {
    return this.context.model.getNodeLikeDatum(this.id);
  }

  get childrenData() {
    return this.context.model.getChildrenData(this.id);
  }

  getLabelStyle(attributes) {
    const [width, height] = this.getSize(attributes);
    return {
      x: -width / 2 + 8,
      y: -height / 2 + 16,
      text: this.data.name,
      fontSize: 12,
      opacity: 0.85,
      fill: '#000',
      cursor: 'pointer',
    };
  }

  getPriceStyle(attributes) {
    const [width, height] = this.getSize(attributes);
    return {
      x: -width / 2 + 8,
      y: height / 2 - 8,
      text: this.data.label,
      fontSize: 16,
      fill: '#000',
      opacity: 0.85,
    };
  }

  drawPriceShape(attributes, container) {
    const priceStyle = this.getPriceStyle(attributes);
    this.upsert('price', GText, priceStyle, container);
  }

  getCurrencyStyle(attributes) {
    const [, height] = this.getSize(attributes);
    return {
      x: this.shapeMap['price'].getLocalBounds().max[0] + 4,
      y: height / 2 - 8,
      text: this.data.currency,
      fontSize: 12,
      fill: '#000',
      opacity: 0.75,
    };
  }

  drawCurrencyShape(attributes, container) {
    const currencyStyle = this.getCurrencyStyle(attributes);
    this.upsert('currency', GText, currencyStyle, container);
  }

  getPercentStyle(attributes) {
    const [width, height] = this.getSize(attributes);
    return {
      x: width / 2 - 4,
      y: height / 2 - 8,
      text: `${((Number(this.data.variableValue) || 0) * 100).toFixed(2)}%`,
      fontSize: 12,
      textAlign: 'right',
      fill: COLORS[this.data.status],
    };
  }

  drawPercentShape(attributes, container) {
    const percentStyle = this.getPercentStyle(attributes);
    this.upsert('percent', GText, percentStyle, container);
  }

  getTriangleStyle(attributes) {
    const percentMinX = this.shapeMap['percent'].getLocalBounds().min[0];
    const [, height] = this.getSize(attributes);
    return {
      fill: COLORS[this.data.status],
      x: this.data.variableUp ? percentMinX - 18 : percentMinX,
      y: height / 2 - 16,
      fontFamily: 'iconfont',
      fontSize: 16,
      text: '\ue62d',
      transform: this.data.variableUp ? [] : [['rotate', 180]],
    };
  }

  drawTriangleShape(attributes, container) {
    const triangleStyle = this.getTriangleStyle(attributes);
    this.upsert('triangle', Label, triangleStyle, container);
  }

  getVariableStyle(attributes) {
    const [, height] = this.getSize(attributes);
    return {
      fill: '#000',
      fontSize: 12,
      opacity: 0.45,
      text: this.data.variableName,
      textAlign: 'right',
      x: this.shapeMap['triangle'].getLocalBounds().min[0] - 4,
      y: height / 2 - 8,
    };
  }

  drawVariableShape(attributes, container) {
    const variableStyle = this.getVariableStyle(attributes);
    this.upsert('variable', GText, variableStyle, container);
  }

  getCollapseStyle(attributes) {
    if (this.childrenData.length === 0) return false;
    const { collapsed } = attributes;
    const [width, height] = this.getSize(attributes);
    return {
      backgroundFill: '#fff',
      backgroundHeight: 16,
      backgroundLineWidth: 1,
      backgroundRadius: 0,
      backgroundStroke: GREY_COLOR,
      backgroundWidth: 16,
      cursor: 'pointer',
      fill: GREY_COLOR,
      fontSize: 16,
      text: collapsed ? '+' : '-',
      textAlign: 'center',
      textBaseline: 'middle',
      x: width / 2,
      y: 0,
    };
  }

  drawCollapseShape(attributes, container) {
    const collapseStyle = this.getCollapseStyle(attributes);
    const btn = this.upsert('collapse', Badge, collapseStyle, container);

    if (btn && !Reflect.has(btn, '__bind__')) {
      Reflect.set(btn, '__bind__', true);
      btn.addEventListener(CommonEvent.CLICK, () => {
        const { collapsed } = this.attributes;
        const graph = this.context.graph;
        if (collapsed) graph.expandElement(this.id);
        else graph.collapseElement(this.id);
      });
    }
  }

  getProcessBarStyle(attributes) {
    const { rate, status } = this.data;
    const { radius } = attributes;
    const color = COLORS[status];
    const percent = `${Number(rate) * 100}%`;
    const [width, height] = this.getSize(attributes);
    return {
      x: -width / 2,
      y: height / 2 - 4,
      width: width,
      height: 4,
      radius: [0, 0, radius, radius],
      fill: `linear-gradient(to right, ${color} ${percent}, ${GREY_COLOR} ${percent})`,
    };
  }

  drawProcessBarShape(attributes, container) {
    const processBarStyle = this.getProcessBarStyle(attributes);
    this.upsert('process-bar', GRect, processBarStyle, container);
  }

  getKeyStyle(attributes) {
    const keyStyle = super.getKeyStyle(attributes);
    return {
      ...keyStyle,
      fill: '#fff',
      lineWidth: 1,
      stroke: GREY_COLOR,
    };
  }

  render(attributes = this.parsedAttributes, container) {
    super.render(attributes, container);

    this.drawPriceShape(attributes, container);
    this.drawCurrencyShape(attributes, container);
    this.drawPercentShape(attributes, container);
    this.drawTriangleShape(attributes, container);
    this.drawVariableShape(attributes, container);
    this.drawProcessBarShape(attributes, container);
    this.drawCollapseShape(attributes, container);
  }
}

register(ExtensionCategory.NODE, 'tree-node', TreeNode);

fetch('https://assets.antv.antgroup.com/g6/decision-tree.json')
  .then((res) => res.json())
  .then((data) => {
    const graph = new Graph({
      container: 'container',
      data: treeToGraphData(data, {
        getNodeData: (datum, depth) => {
          if (!datum.style) datum.style = {};
          datum.style.collapsed = depth >= 2;
          if (!datum.children) return datum;
          const { children, ...restDatum } = datum;
          return { ...restDatum, children: children.map((child) => child.id) };
        },
      }),
      node: {
        type: 'tree-node',
        style: {
          size: [202, 60],
          ports: [{ placement: 'left' }, { placement: 'right' }],
          radius: 4,
        },
      },
      edge: {
        type: 'cubic-horizontal',
        style: {
          stroke: GREY_COLOR,
        },
      },
      layout: {
        type: 'indented',
        direction: 'LR',
        dropCap: false,
        indent: 300,
        getHeight: () => 60,
        preLayout: false,
      },
      behaviors: ['zoom-canvas', 'drag-canvas'],
    });

    graph.once(GraphEvent.AFTER_RENDER, () => {
      graph.fitView();
    });

    graph.render();
  });
```

### Example Data

```json
{
  "id": "g1",
  "name": "Name1",
  "count": 123456,
  "label": "538.90",
  "currency": "Yuan",
  "rate": 1,
  "status": "B",
  "variableName": "V1",
  "variableValue": 0.341,
  "variableUp": false,
  "children": [
    {
      "id": "g12",
      "name": "Deal with LONG label LONG label LONG label LONG label",
      "count": 123456,
      "label": "338.00",
      "rate": 0.627,
      "status": "R",
      "currency": "Yuan",
      "variableName": "V2",
      "variableValue": 0.179,
      "variableUp": true,
      "children": [
        {
          "id": "g121",
          "name": "Name3",
          "collapsed": true,
          "count": 123456,
          "label": "138.00",
          "rate": 0.123,
          "status": "B",
          "currency": "Yuan",
          "variableName": "V2",
          "variableValue": 0.27,
          "variableUp": true,
          "children": [
            {
              "id": "g1211",
              "name": "Name4",
              "count": 123456,
              "label": "138.00",
              "rate": 1,
              "status": "B",
              "currency": "Yuan",
              "variableName": "V1",
              "variableValue": 0.164,
              "variableUp": false,
              "children": []
            }
          ]
        },
        {
          "id": "g122",
          "name": "Name5",
          "collapsed": true,
          "count": 123456,
          "label": "100.00",
          "rate": 0.296,
          "status": "G",
          "currency": "Yuan",
          "variableName": "V1",
          "variableValue": 0.259,
          "variableUp": true,
          "children": [
            {
              "id": "g1221",
              "name": "Name6",
              "count": 123456,
              "label": "40.00",
              "rate": 0.4,
              "status": "G",
              "currency": "Yuan",
              "variableName": "V1",
              "variableValue": 0.135,
              "variableUp": true,
              "children": [
                {
                  "id": "g12211",
                  "name": "Name6-1",
                  "count": 123456,
                  "label": "40.00",
                  "rate": 1,
                  "status": "R",
                  "currency": "Yuan",
                  "variableName": "V1",
                  "variableValue": 0.181,
                  "variableUp": true,
                  "children": []
                }
              ]
            },
            {
              "id": "g1222",
              "name": "Name7",
              "count": 123456,
              "label": "60.00",
              "rate": 0.6,
              "status": "G",
              "currency": "Yuan",
              "variableName": "V1",
              "variableValue": 0.239,
              "variableUp": false,
              "children": []
            }
          ]
        },
        {
          "id": "g123",
          "name": "Name8",
          "collapsed": true,
          "count": 123456,
          "label": "100.00",
          "rate": 0.296,
          "status": "DI",
          "currency": "Yuan",
          "variableName": "V2",
          "variableValue": 0.131,
          "variableUp": false,
          "children": [
            {
              "id": "g1231",
              "name": "Name8-1",
              "count": 123456,
              "label": "100.00",
              "rate": 1,
              "status": "DI",
              "currency": "Yuan",
              "variableName": "V2",
              "variableValue": 0.131,
              "variableUp": false,
              "children": []
            }
          ]
        }
      ]
    },
    {
      "id": "g13",
      "name": "Name9",
      "count": 123456,
      "label": "100.90",
      "rate": 0.187,
      "status": "B",
      "currency": "Yuan",
      "variableName": "V2",
      "variableValue": 0.221,
      "variableUp": true,
      "children": [
        {
          "id": "g131",
          "name": "Name10",
          "count": 123456,
          "label": "33.90",
          "rate": 0.336,
          "status": "R",
          "currency": "Yuan",
          "variableName": "V1",
          "variableValue": 0.12,
          "variableUp": true,
          "children": []
        },
        {
          "id": "g132",
          "name": "Name11",
          "count": 123456,
          "label": "67.00",
          "rate": 0.664,
          "status": "G",
          "currency": "Yuan",
          "variableName": "V1",
          "variableValue": 0.241,
          "variableUp": false,
          "children": []
        }
      ]
    },
    {
      "id": "g14",
      "name": "Name12",
      "count": 123456,
      "label": "100.00",
      "rate": 0.186,
      "status": "G",
      "currency": "Yuan",
      "variableName": "V2",
      "variableValue": 0.531,
      "variableUp": true,
      "children": []
    }
  ]
}
```