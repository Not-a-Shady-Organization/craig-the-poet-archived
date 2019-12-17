import React from 'react';
// https://www.npmjs.com/package/react-draggable
import Draggable from 'react-draggable';


class Frame extends React.Component {

  constructor(props) {
    super(props)

    this.onDrag = this.onDrag.bind(this);
  }

  onDrag(event, data) {
    this.props.onChange(data.node.id, data.lastX)
  }

  render() {
    return(
      <div className="frame">
        <Draggable
          axis="x"
          onDrag={this.onDrag}
          bounds={this.props.bounds}
          defaultPosition={{x: this.props.position, y: 0}}
        >
          <img
            id={this.props.id}
            src={this.props.src}
            style={{ width: this.props.imageWidth }}
            className="frame-image"
            draggable="false" // Turn off default browser dragging feature
          />
        </Draggable>
      </div>
    )
  }
}

export default Frame;
