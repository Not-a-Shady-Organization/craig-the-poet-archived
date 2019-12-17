import React from 'react';
// https://www.npmjs.com/package/react-draggable
import Draggable from 'react-draggable';
import Frame from './Frame.js';



function getWidth() {
  return Math.max(
    document.body.scrollWidth,
    document.documentElement.scrollWidth,
    document.body.offsetWidth,
    document.documentElement.offsetWidth,
    document.documentElement.clientWidth
  );
}


class Timeline extends React.Component {

  constructor(props) {
    super(props)

    this.onDrag = this.onDrag.bind(this)
  }

  timePositionToPixelPosition(time) {
    return time/this.props.totalTime * this.props.timelineWidth - this.props.timelineWidth/2
  }

  pixelPositionToTimePosition(pixel) {
    return (pixel + this.props.timelineWidth/2) / this.props.timelineWidth * this.props.totalTime
  }

  onDrag(id, pixelPosition) {
    let timePosition = this.pixelPositionToTimePosition(pixelPosition)
    this.props.onChange(id, timePosition)
  }



  render() {
    let elementList = []

    for(let id in this.props.frames) {
      let timePosition = this.props.frames[id]['timePosition']
      let pixelPosition = this.timePositionToPixelPosition(this.props.frames[id]['timePosition'])

      elementList.push(
        <>
          <Frame
            id={id}
            src={this.props.frames[id]['src']}
            bounds={{
              left:-this.props.timelineWidth/2,
              right:this.props.timelineWidth/2,
              top:0,
              bottom:0
            }}
            imageWidth={this.props.imageWidth}
            position={pixelPosition}
            onChange={this.onDrag}
          />
          <div
            id={id + '-timecode'}
            class="timecode"
            style={{
              // TODO: Oof this getWidth thing is shite
              left: .15 * getWidth() + pixelPosition + this.props.timelineWidth/2,
              marginTop: '-1.5em'
            }}
          >
            {this.props.frames[id]['timePosition'].toFixed(2)}
          </div>
        </>
      )
    }

    return(
      <div id="timeline-container" style={{ width: this.props.timelineWidth+100}}>
        {elementList}
        <hr
          id="timeline"
          style={{
            width: this.props.timelineWidth,
          }}
        />
      </div>
    )
  }
}

export default Timeline;
